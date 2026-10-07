local_library <- Sys.getenv("REPLICATION_R_LIB", "")
if (nzchar(local_library)) .libPaths(c(local_library, .libPaths()))
set.seed(20260728)
suppressPackageStartupMessages({
  library(contdid)
  library(dplyr)
  library(readr)
  library(tibble)
})

# ==============================================================================
# Estimates_contDID_v1.R
#
# Purpose
# -------
# Produce the continuous-DiD alternatives for version 1 of the analysis.
# The preferred estimator is now the Stata TWFE specification with CNO4 and
# CNO1-by-month fixed effects. This file asks how far the public contdid
# estimator can be adapted to the same economic comparison without claiming
# that outcome residualization is equivalent to covariate-adjusted ContDID.
#
# Alternatives
# ------------
# CDID 1: CNO1-stratified ContDID.
#   Estimate ContDID separately within CNO1 families containing at least 15
#   positive-exposure and 5 zero-exposure occupations. Aggregate family-
#   specific ACRT paths using positive-exposure occupation shares. The support
#   rule prevents flexible dose-response slopes from being fitted in families
#   with too little within-family exposure variation.
#
# CDID 2: Control-based CNO1-by-month adjustment.
#   For supported families, subtract the CNO1-by-month outcome change observed
#   among zero-exposure occupations, relative to October 2022, and run pooled
#   ContDID on the adjusted outcome. This is a transparent two-step diagnostic,
#   not an exact implementation of conditional ContDID.
#
# CDID 3: Unconditional ContDID benchmark.
#   This reproduces the pooled comparison without family-specific adjustment.
#
# Timing and scale
# ----------------
# November 2022 is event time 0, December 2022 is event time 1, and October
# 2022 is the omitted reference month. Dose equals exposure / 0.10, so a
# one-unit marginal effect corresponds to 10 percentage points of exposure.
#
# The age input includes audited May 2024 backcasts obtained by inverting
# SEPE's June-over-May CNO4-by-age growth rates. The notebook preserves a
# source flag and leaves every ambiguous cell missing.
# ==============================================================================

script_args <- commandArgs(trailingOnly = FALSE)
script_file <- sub("^--file=", "", script_args[grepl("^--file=", script_args)])
script_dir <- if (length(script_file) == 1L) {
  dirname(normalizePath(script_file, winslash = "/", mustWork = TRUE))
} else {
  normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

input_dir <- file.path(script_dir, "data", "prepared")
output_root <- file.path(script_dir, "intermediate")
tables_dir <- output_root
figures_dir <- output_root
logs_dir <- file.path(script_dir, "logs")

dir.create(tables_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(logs_dir, recursive = TRUE, showWarnings = FALSE)

# Remove files from the temporary unrestricted-versus-restricted comparison.
legacy_support_outputs <- list.files(
  tables_dir,
  pattern = "cno1_stratified_restricted_15_5|contdid_support_comparison_v1",
  full.names = TRUE
)
if (length(legacy_support_outputs) > 0L) unlink(legacy_support_outputs)

event_period <- "2022-11"
event_min <- -21L
event_max <- 40L
reference_event <- -1L
restricted_min_positive <- 15L
restricted_min_zero <- 5L

biters_env <- suppressWarnings(as.integer(Sys.getenv("CONTDID_BITERS", "1000")))
biters <- ifelse(is.na(biters_env) || biters_env < 1L, 1000L, biters_env)
v1_smoke <- identical(Sys.getenv("V1_CONTDID_SMOKE"), "1")
v1_no2021_only <- identical(Sys.getenv("V1_CONTDID_NO2021_ONLY"), "1")

safe_name <- function(x) {
  x |>
    as.character() |>
    gsub("<", "lt", x = _) |>
    gsub(">", "gt", x = _) |>
    gsub("[^A-Za-z0-9]+", "_", x = _) |>
    tolower()
}

read_panel <- function(filename) {
  read_csv(
    file.path(input_dir, filename),
    show_col_types = FALSE,
    col_types = cols(.default = col_character())
  ) |>
    mutate(
      across(
        any_of(c(
          "ym_index", "ym_stata", "parados", "contratos", "ln_parados",
          "ln_contratos", "ln_parados_p1", "ln_contratos_p1",
          "exposure_nearest", "exposure_10pp", "exposure_weighted",
          "exposure_weighted_10pp", "post_nov2022", "may2024_age_backcast"
        )),
        ~ suppressWarnings(as.numeric(.x))
      ),
      cno4 = sprintf("%04s", cno4),
      cno1d = as.integer(cno1d),
      id = as.integer(factor(unit)),
      const = 1
    )
}

make_contdid_data <- function(df, outcome, dose_var = "exposure_10pp") {
  shock_index <- df |>
    filter(period == event_period) |>
    distinct(ym_index) |>
    pull(ym_index)

  if (length(shock_index) != 1L) {
    stop("Could not locate November 2022 in the prepared panel.")
  }

  df |>
    mutate(
      dose = .data[[dose_var]],
      y = .data[[outcome]],
      # The first treated cohort is coded in December. The package's event
      # index is shifted below so November remains event time 0 in every method.
      g = if_else(dose > 0, shock_index + 1, 0)
    ) |>
    filter(!is.na(y), !is.na(dose), dose >= 0) |>
    select(id, unit, cno4, cno1d, period, ym_index, g, dose, y, const)
}

# contdid's exported wrapper has changed across development versions. This
# centralized adapter uses the package internals already required by the
# project's installed version and leaves every modeling choice explicit.
cont_did_fixed <- function(
    data,
    aggregation = c("eventstudy", "dose"),
    target_parameter = c("slope", "level"),
    dvals = NULL,
    degree = 2L,
    num_knots = 1L,
    cband = TRUE,
    biters = biters) {

  aggregation <- match.arg(aggregation)
  target_parameter <- match.arg(target_parameter)
  xformula <- ~1
  treatment_type <- "continuous"
  base_period <- "varying"
  anticipation <- 0
  control_group <- "nevertreated"

  attgt_fun <- contdid:::cont_did_acrt
  gt_type <- ifelse(aggregation == "eventstudy", "att", "dose")

  setup_fun <- function(
      yname, gname, tname, idname, data, panel = TRUE, cband = cband,
      alp = 0.05, boot_type = "multiplier", gt_type = gt_type,
      weightsname = NULL, ret_quantile = NULL, probs = NULL,
      biters = biters, cl = 1, call = NULL, ...) {

    ptep <- contdid:::setup_pte_cont(
      yname = yname,
      gname = gname,
      tname = tname,
      idname = idname,
      data = data,
      xformula = xformula,
      target_parameter = target_parameter,
      aggregation = aggregation,
      treatment_type = treatment_type,
      required_pre_periods = 1,
      anticipation = anticipation,
      base_period = base_period,
      cband = cband,
      alp = alp,
      boot_type = boot_type,
      weightsname = weightsname,
      gt_type = gt_type,
      biters = biters,
      cl = cl,
      dname = "dose",
      dvals = dvals,
      degree = degree,
      num_knots = num_knots,
      panel = panel,
      ret_quantile = ret_quantile,
      probs = probs,
      call = call
    )
    ptep$control_group <- control_group
    ptep
  }

  ptetools::pte(
    yname = "y",
    gname = "g",
    tname = "ym_index",
    idname = "id",
    data = data,
    setup_pte_fun = setup_fun,
    subset_fun = contdid:::cont_two_by_two_subset,
    attgt_fun = attgt_fun,
    cband = cband,
    alp = 0.05,
    boot_type = "multiplier",
    gt_type = gt_type,
    biters = biters,
    cl = 1,
    control_group = control_group,
    anticipation = anticipation,
    base_period = base_period,
    dose_est_method = "parametric",
    dvals = dvals,
    degree = degree,
    num_knots = num_knots
  )
}

extract_event <- function(object) {
  event <- object$event_study
  aligned_time <- as.integer(event$egt) + 1L
  keep <- aligned_time >= event_min & aligned_time <= event_max
  influence <- event$inf.function$dynamic.inf.func.e

  if (is.null(influence)) {
    stop("ContDID did not return dynamic influence functions.")
  }
  if (ncol(influence) != length(aligned_time)) {
    stop("Influence-function columns do not match event-study periods.")
  }

  list(
    table = tibble(
      event_time = aligned_time[keep],
      estimate = as.numeric(event$att.egt[keep]),
      std_error = as.numeric(event$se.egt[keep])
    ) |>
      mutate(
        ci_low = estimate - 1.96 * std_error,
        ci_high = estimate + 1.96 * std_error
      ),
    covariance = crossprod(influence[, keep, drop = FALSE]) / nrow(influence)^2,
    influence_rows = nrow(influence)
  )
}

average_post <- function(event_table, covariance) {
  post_index <- which(event_table$event_time >= 1L & event_table$event_time <= event_max)
  weights <- rep(1 / length(post_index), length(post_index))
  covariance_post <- covariance[post_index, post_index, drop = FALSE]
  estimate <- sum(weights * event_table$estimate[post_index])
  standard_error <- sqrt(drop(t(weights) %*% covariance_post %*% weights))

  tibble(
    estimate = estimate,
    std_error = standard_error,
    ci_low = estimate - 1.96 * standard_error,
    ci_high = estimate + 1.96 * standard_error,
    effect_percent = 100 * estimate,
    post_start = min(event_table$event_time[post_index]),
    post_end = max(event_table$event_time[post_index]),
    post_periods = length(post_index)
  )
}

phase_average <- function(event_table, covariance) {
  phase_definitions <- list(adjustment = 0L:24L, later = 25L:40L)
  phase_weights <- lapply(phase_definitions, function(periods) {
    index <- which(event_table$event_time %in% periods)
    if (length(index) != length(periods)) {
      stop("ContDID event path does not cover every requested phase month.")
    }
    weights <- rep(0, nrow(event_table))
    weights[index] <- 1 / length(index)
    weights
  })

  summarize_phase <- function(name) {
    weights <- phase_weights[[name]]
    estimate <- sum(weights * event_table$estimate)
    standard_error <- sqrt(drop(t(weights) %*% covariance %*% weights))
    tibble(
      phase = name,
      event_start = min(phase_definitions[[name]]),
      event_end = max(phase_definitions[[name]]),
      estimate = estimate,
      std_error = standard_error,
      ci_low = estimate - 1.96 * standard_error,
      ci_high = estimate + 1.96 * standard_error,
      effect_percent = 100 * estimate
    )
  }

  difference_weights <- phase_weights$adjustment - phase_weights$later
  difference <- sum(difference_weights * event_table$estimate)
  difference_se <- sqrt(drop(
    t(difference_weights) %*% covariance %*% difference_weights
  ))
  equality_p <- if (difference_se > 0) {
    2 * pnorm(-abs(difference / difference_se))
  } else {
    NA_real_
  }

  bind_rows(lapply(names(phase_definitions), summarize_phase)) |>
    mutate(equality_p = equality_p)
}

generalized_inverse <- function(matrix, tolerance = sqrt(.Machine$double.eps)) {
  matrix <- (matrix + t(matrix)) / 2
  decomposition <- eigen(matrix, symmetric = TRUE)
  cutoff <- tolerance * max(1, max(abs(decomposition$values)))
  keep <- decomposition$values > cutoff
  if (!any(keep)) {
    return(list(inverse = matrix * 0, rank = 0L))
  }
  vectors <- decomposition$vectors[, keep, drop = FALSE]
  inverse <- vectors %*%
    diag(1 / decomposition$values[keep], nrow = sum(keep)) %*%
    t(vectors)
  list(inverse = inverse, rank = sum(keep))
}

wald_test <- function(coefficients, covariance, restrictions) {
  restricted_coefficients <- drop(restrictions %*% coefficients)
  restricted_covariance <- restrictions %*% covariance %*% t(restrictions)
  inverse <- generalized_inverse(restricted_covariance)
  if (inverse$rank == 0L) {
    return(tibble(statistic = NA_real_, degrees_freedom = 0L, p_value = NA_real_))
  }
  statistic <- drop(
    t(restricted_coefficients) %*% inverse$inverse %*% restricted_coefficients
  )
  tibble(
    statistic = statistic,
    degrees_freedom = inverse$rank,
    p_value = pchisq(statistic, df = inverse$rank, lower.tail = FALSE)
  )
}

pretrend_diagnostics <- function(event_table, covariance) {
  windows <- list(
    "full_-21_-2" = -21L:-2L,
    "early_-21_-10" = -21L:-10L,
    "recent_-10_-2" = -10L:-2L
  )

  bind_rows(lapply(names(windows), function(window_name) {
    index <- which(event_table$event_time %in% windows[[window_name]])
    coefficients <- event_table$estimate[index]
    covariance_window <- covariance[index, index, drop = FALSE]
    coefficient_count <- length(coefficients)
    if (coefficient_count < 2L) return(NULL)

    joint_zero <- wald_test(
      coefficients,
      covariance_window,
      diag(coefficient_count)
    ) |>
      mutate(test = "joint_equal_zero")

    equality_restrictions <- matrix(0, nrow = coefficient_count - 1L, ncol = coefficient_count)
    equality_restrictions[cbind(seq_len(coefficient_count - 1L), seq_len(coefficient_count - 1L))] <- 1
    equality_restrictions[, coefficient_count] <- -1
    equal_coefficients <- wald_test(
      coefficients,
      covariance_window,
      equality_restrictions
    ) |>
      mutate(test = "joint_equal_coefficients")

    bind_rows(joint_zero, equal_coefficients) |>
      mutate(
        window = window_name,
        event_start = min(event_table$event_time[index]),
        event_end = max(event_table$event_time[index]),
        coefficients = coefficient_count,
        .before = 1
      )
  }))
}

write_covariance <- function(covariance, event_time, specification, outcome) {
  out <- as_tibble(covariance, .name_repair = "minimal")
  names(out) <- paste0("cov_", seq_along(event_time))
  out <- bind_cols(
    tibble(
      specification = specification,
      outcome = outcome,
      event_time = event_time
    ),
    out
  )
  write_csv(
    out,
    file.path(tables_dir, paste0(
      "contdid_covariance_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
}

support_by_cno1 <- function(
    df,
    dose_var = "exposure_10pp",
    support_rule = c("restricted_15_5", "unrestricted")) {
  support_rule <- match.arg(support_rule)

  support <- df |>
    distinct(cno4, cno1d, dose = .data[[dose_var]]) |>
    group_by(cno1d) |>
    summarise(
      occupations = n(),
      positive_occupations = sum(dose > 0, na.rm = TRUE),
      zero_occupations = sum(dose == 0, na.rm = TRUE),
      distinct_positive_doses = n_distinct(dose[dose > 0 & !is.na(dose)]),
      mean_dose = mean(dose, na.rm = TRUE),
      sd_dose = sd(dose, na.rm = TRUE),
      min_dose = min(dose, na.rm = TRUE),
      max_dose = max(dose, na.rm = TRUE),
      .groups = "drop"
    )

  support |>
    mutate(
      support_rule = .env$support_rule,
      candidate = if (.env$support_rule == "restricted_15_5") {
        positive_occupations >= restricted_min_positive &
          zero_occupations >= restricted_min_zero
      } else {
        positive_occupations > 0 & zero_occupations > 0
      },
      candidate_reason = case_when(
        positive_occupations == 0 ~ "no positive-exposure occupations",
        zero_occupations == 0 ~ "no zero-exposure occupations",
        .env$support_rule == "restricted_15_5" &
          positive_occupations < restricted_min_positive ~
          "fewer than 15 positive-exposure occupations",
        .env$support_rule == "restricted_15_5" &
          zero_occupations < restricted_min_zero ~
          "fewer than 5 zero-exposure occupations",
        TRUE ~ "candidate"
      )
    )
}

fit_pooled_event <- function(df, outcome, specification, dose_var = "exposure_10pp") {
  data <- make_contdid_data(df, outcome, dose_var) |>
    group_by(id) |>
    filter(n_distinct(ym_index) == n_distinct(df$ym_index)) |>
    ungroup()

  object <- cont_did_fixed(
    data,
    aggregation = "eventstudy",
    target_parameter = "slope",
    cband = TRUE,
    biters = biters
  )
  extracted <- extract_event(object)
  event <- extracted$table |>
    mutate(
      specification = specification,
      outcome = outcome,
      dose_var = dose_var,
      units = n_distinct(data$id),
      biters = biters,
      .before = 1
    )
  average <- average_post(event, extracted$covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      dose_var = dose_var,
      units = n_distinct(data$id),
      observations = nrow(data),
      covariance_source = "dynamic influence functions",
      biters = biters,
      .before = 1
    )
  phases <- phase_average(event, extracted$covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      dose_var = dose_var,
      units = n_distinct(data$id),
      observations = nrow(data),
      covariance_source = "dynamic influence functions",
      biters = biters,
      .before = 1
    )
  pretrends <- pretrend_diagnostics(event, extracted$covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      units = n_distinct(data$id),
      observations = nrow(data),
      .before = 1
    )

  write_csv(
    event,
    file.path(tables_dir, paste0(
      "contdid_event_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    average,
    file.path(tables_dir, paste0(
      "contdid_average_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    phases,
    file.path(tables_dir, paste0(
      "contdid_phase_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    pretrends,
    file.path(tables_dir, paste0(
      "contdid_pretrend_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_covariance(extracted$covariance, event$event_time, specification, outcome)

  list(event = event, average = average, phases = phases, pretrends = pretrends,
       covariance = extracted$covariance)
}

fit_stratified_event <- function(
    df,
    outcome,
    specification,
    dose_var = "exposure_10pp",
    support_rule = c("restricted_15_5", "unrestricted")) {
  support_rule <- match.arg(support_rule)
  support <- support_by_cno1(df, dose_var, support_rule)
  candidate_groups <- support |>
    filter(candidate) |>
    pull(cno1d)

  if (length(candidate_groups) == 0L) {
    stop("No CNO1 family has positive- and zero-exposure support.")
  }

  fits <- list()
  attempts <- list()
  for (family in candidate_groups) {
    family_df <- df |> filter(cno1d == family)
    family_data <- make_contdid_data(family_df, outcome, dose_var) |>
      group_by(id) |>
      filter(n_distinct(ym_index) == n_distinct(family_df$ym_index)) |>
      ungroup()

    effective_support <- family_data |>
      distinct(id, dose) |>
      summarise(
        effective_positive_occupations = sum(dose > 0, na.rm = TRUE),
        effective_zero_occupations = sum(dose == 0, na.rm = TRUE),
        effective_distinct_positive_doses = n_distinct(dose[dose > 0 & !is.na(dose)]),
        effective_units = n()
      )

    if (effective_support$effective_positive_occupations == 0L ||
        effective_support$effective_zero_occupations == 0L) {
      attempts[[as.character(family)]] <- effective_support |>
        mutate(
          cno1d = family,
          estimation_success = FALSE,
          estimation_reason = "outcome-complete panel lacks positive or zero exposure support",
          .before = 1
        )
      next
    }

    message("  CNO1 ", family, ": ", outcome, " [", support_rule, "]")
    fit_attempt <- tryCatch({
      object <- cont_did_fixed(
        family_data,
        aggregation = "eventstudy",
        target_parameter = "slope",
        cband = FALSE,
        biters = biters
      )
      extract_event(object)
    }, error = function(error) error)

    if (inherits(fit_attempt, "error")) {
      attempts[[as.character(family)]] <- effective_support |>
        mutate(
          cno1d = family,
          estimation_success = FALSE,
          estimation_reason = conditionMessage(fit_attempt),
          .before = 1
        )
      message("    skipped: ", conditionMessage(fit_attempt))
      next
    }

    fits[[as.character(family)]] <- list(
      event = fit_attempt$table,
      covariance = fit_attempt$covariance,
      average = average_post(fit_attempt$table, fit_attempt$covariance),
      positive_occupations = effective_support$effective_positive_occupations,
      zero_occupations = effective_support$effective_zero_occupations,
      units = effective_support$effective_units
    )
    attempts[[as.character(family)]] <- effective_support |>
      mutate(
        cno1d = family,
        estimation_success = TRUE,
        estimation_reason = "estimated",
        .before = 1
      )
  }

  if (length(fits) == 0L) {
    stop("No candidate CNO1 family could be estimated.")
  }

  attempts <- bind_rows(attempts)
  support <- support |>
    left_join(attempts, by = "cno1d") |>
    mutate(
      estimation_attempted = candidate,
      estimation_success = coalesce(estimation_success, FALSE),
      estimation_reason = case_when(
        !candidate ~ candidate_reason,
        is.na(estimation_reason) ~ "not estimated",
        TRUE ~ estimation_reason
      ),
      retained = estimation_success
    )

  retained_positive <- sum(
    support$effective_positive_occupations[support$retained],
    na.rm = TRUE
  )
  if (retained_positive <= 0) {
    stop("Estimated CNO1 families contain no positive-exposure occupations.")
  }
  support <- support |>
    mutate(
      positive_weight = if_else(
        retained,
        effective_positive_occupations / retained_positive,
        0
      )
    )

  for (name in names(fits)) {
    family <- as.integer(name)
    fits[[name]]$weight <- support$positive_weight[support$cno1d == family]
  }

  common_time <- Reduce(
    intersect,
    lapply(fits, function(x) x$event$event_time)
  ) |>
    sort()
  weights <- vapply(fits, function(x) x$weight, numeric(1))
  weights <- weights / sum(weights)

  aggregate_estimate <- rep(0, length(common_time))
  aggregate_covariance <- matrix(0, length(common_time), length(common_time))
  for (name in names(fits)) {
    fit <- fits[[name]]
    index <- match(common_time, fit$event$event_time)
    aggregate_estimate <- aggregate_estimate + fit$weight * fit$event$estimate[index]
    aggregate_covariance <- aggregate_covariance +
      fit$weight^2 * fit$covariance[index, index, drop = FALSE]
  }

  # The manuscript's dynamic panel predates the outcome-completeness weights
  # used by its updated phase table. Reproduce that panel's population weights
  # explicitly; keep phase inference on the effective estimation sample.
  if (specification == "cno1_stratified") {
    plot_weights <- support$positive_occupations[support$retained]
    plot_weights <- plot_weights / sum(plot_weights)
    plot_estimate <- rep(0, length(common_time))
    plot_covariance <- matrix(0, length(common_time), length(common_time))
    for (i in seq_along(fits)) {
      fit <- fits[[i]]
      index <- match(common_time, fit$event$event_time)
      plot_estimate <- plot_estimate + plot_weights[i] * fit$event$estimate[index]
      plot_covariance <- plot_covariance +
        plot_weights[i]^2 * fit$covariance[index, index, drop = FALSE]
    }
    plot_se <- sqrt(diag(plot_covariance))
    write_csv(tibble(event_time = common_time, estimate = plot_estimate,
                     std_error = plot_se,
                     ci_low = plot_estimate - 1.96 * plot_se,
                     ci_high = plot_estimate + 1.96 * plot_se),
              file.path(tables_dir, paste0("contdid_figure_event_", specification,
                                          "_", outcome, ".csv")))
  }

  aggregate_se <- sqrt(diag(aggregate_covariance))
  event <- tibble(
    specification = specification,
    outcome = outcome,
    dose_var = dose_var,
    event_time = common_time,
    estimate = aggregate_estimate,
    std_error = aggregate_se,
    ci_low = aggregate_estimate - 1.96 * aggregate_se,
    ci_high = aggregate_estimate + 1.96 * aggregate_se,
    supported_cno1_groups = length(fits),
    aggregation_weight = "positive-exposure occupation share"
  )
  retained_zero <- sum(
    support$effective_zero_occupations[support$retained],
    na.rm = TRUE
  )
  total_positive <- sum(support$positive_occupations, na.rm = TRUE)
  coverage_share <- retained_positive / total_positive
  average <- average_post(event, aggregate_covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      dose_var = dose_var,
      supported_cno1_groups = length(fits),
      supported_positive_occupations = retained_positive,
      supported_zero_occupations = retained_zero,
      positive_exposure_coverage = coverage_share,
      support_rule = support_rule,
      covariance_source = "weighted sum of disjoint-family IF covariance matrices",
      biters = biters,
      observations = sum(vapply(fits, function(x) x$units, numeric(1))) *
        n_distinct(df$ym_index),
      .before = 1
    )
  phases <- phase_average(event, aggregate_covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      dose_var = dose_var,
      supported_cno1_groups = length(fits),
      supported_positive_occupations = retained_positive,
      supported_zero_occupations = retained_zero,
      positive_exposure_coverage = coverage_share,
      support_rule = support_rule,
      covariance_source = "weighted sum of disjoint-family IF covariance matrices",
      biters = biters,
      observations = sum(vapply(fits, function(x) x$units, numeric(1))) *
        n_distinct(df$ym_index),
      .before = 1
    )
  pretrends <- pretrend_diagnostics(event, aggregate_covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      supported_cno1_groups = length(fits),
      supported_positive_occupations = retained_positive,
      positive_exposure_coverage = coverage_share,
      support_rule = support_rule,
      .before = 1
    )

  family_diagnostics <- bind_rows(lapply(names(fits), function(name) {
    family <- as.integer(name)
    fit <- fits[[name]]
    fit$average |>
      mutate(
        cno1d = family,
        positive_weight = fit$weight,
        positive_occupations = fit$positive_occupations,
        zero_occupations = fit$zero_occupations,
        units = fit$units,
        .before = 1
      )
  }))

  write_csv(
    event,
    file.path(tables_dir, paste0(
      "contdid_event_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    average,
    file.path(tables_dir, paste0(
      "contdid_average_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    phases,
    file.path(tables_dir, paste0(
      "contdid_phase_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    bind_rows(family_diagnostics),
    file.path(tables_dir, paste0(
      "contdid_family_estimates_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    support,
    file.path(tables_dir, paste0(
      "contdid_family_support_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_csv(
    pretrends,
    file.path(tables_dir, paste0(
      "contdid_pretrend_", safe_name(specification), "_", outcome, ".csv"
    ))
  )
  write_covariance(aggregate_covariance, common_time, specification, outcome)

  list(
    event = event,
    average = average,
    phases = phases,
    pretrends = pretrends,
    support = support,
    covariance = aggregate_covariance
  )
}

control_based_adjustment <- function(df, outcome, dose_var = "exposure_10pp") {
  support <- support_by_cno1(df, dose_var, "restricted_15_5")
  supported_groups <- support |>
    filter(candidate) |>
    pull(cno1d)

  supported <- df |>
    filter(cno1d %in% supported_groups)
  reference_index <- supported |>
    filter(period == "2022-10") |>
    distinct(ym_index) |>
    pull(ym_index)
  if (length(reference_index) != 1L) {
    stop("Could not locate October 2022 for the control-based adjustment.")
  }

  zero_path <- supported |>
    filter(.data[[dose_var]] == 0, !is.na(.data[[outcome]])) |>
    group_by(cno1d, ym_index) |>
    summarise(zero_mean = mean(.data[[outcome]]), .groups = "drop")
  zero_reference <- zero_path |>
    filter(ym_index == reference_index) |>
    select(cno1d, zero_reference = zero_mean)

  adjusted_name <- paste0(outcome, "_control_adjusted")
  adjusted <- supported |>
    left_join(zero_path, by = c("cno1d", "ym_index")) |>
    left_join(zero_reference, by = "cno1d") |>
    mutate(
      family_time_change = zero_mean - zero_reference,
      "{adjusted_name}" := .data[[outcome]] - family_time_change
    )

  missing_adjustment <- !is.na(adjusted[[outcome]]) &
    is.na(adjusted$family_time_change)
  if (any(missing_adjustment)) {
    stop("Control-based adjustment has missing CNO1-by-month means for usable outcomes.")
  }

  list(data = adjusted, outcome = adjusted_name, support = support)
}

run_outcome_suite <- function(df, outcome) {
  message("Unconditional ContDID: ", outcome)
  unconditional <- fit_pooled_event(
    df, outcome, "unconditional", "exposure_10pp"
  )

  message("CNO1-stratified ContDID, 15-positive/5-zero support: ", outcome)
  stratified <- fit_stratified_event(
    df,
    outcome,
    "cno1_stratified",
    "exposure_10pp",
    support_rule = "restricted_15_5"
  )

  message("Control-based CNO1-month adjustment: ", outcome)
  adjustment <- control_based_adjustment(df, outcome, "exposure_10pp")
  adjusted <- fit_pooled_event(
    adjustment$data,
    adjustment$outcome,
    "control_based_cno1_month",
    "exposure_10pp"
  )

  list(
    unconditional = unconditional,
    stratified = stratified,
    control_based = adjusted
  )
}

message("ContDID V1: biters = ", biters)
total <- read_panel("est_total_cno4.csv")

support <- support_by_cno1(total, support_rule = "restricted_15_5")
write_csv(support, file.path(tables_dir, "contdid_cno1_support.csv"))

core_results <- list()
for (outcome in c("ln_parados", "ln_contratos")) {
  core_results[[outcome]] <- run_outcome_suite(total, outcome)
  if (v1_smoke) break
}

if (v1_smoke) {
  message("V1_CONTDID_SMOKE=1: smoke test completed.")
  quit(save = "no", status = 0)
}

# The retained robustness columns exclude 2021.
set.seed(20260728)
total_no2021 <- total |>
  filter(period >= "2022-01") |>
  mutate(ym_index = dense_rank(period))
for (outcome in c("ln_parados", "ln_contratos")) {
  fit_stratified_event(total_no2021, outcome, "cno1_stratified_no2021",
                       "exposure_10pp", support_rule = "restricted_15_5")
}

# Production index: one row for every average result produced by this file.
average_files <- list.files(
  tables_dir,
  pattern = "^contdid_average_.*\\.csv$",
  full.names = TRUE
)
index <- bind_rows(lapply(average_files, function(path) {
  read_csv(path, show_col_types = FALSE) |>
    mutate(file = basename(path), .before = 1)
}))
write_csv(index, file.path(tables_dir, "contdid_results_index_v1.csv"))

message("Finished Estimates_contDID_v1.R")
