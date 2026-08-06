suppressPackageStartupMessages({
  library(contdid)
  library(dplyr)
  library(ggplot2)
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
#   Estimate ContDID separately within CNO1 families that have at least
#   15 positive-exposure and 5 zero-exposure occupations. Aggregate the
#   family-specific ACRT paths using positive-exposure occupation shares.
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

event_period <- "2022-11"
event_min <- -21L
event_max <- 40L
reference_event <- -1L
min_positive <- 15L
min_zero <- 5L

biters_env <- suppressWarnings(as.integer(Sys.getenv("CONTDID_BITERS", "1000")))
biters <- ifelse(is.na(biters_env) || biters_env < 1L, 1000L, biters_env)
v1_smoke <- identical(Sys.getenv("V1_CONTDID_SMOKE"), "1")

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
          "exposure_weighted_10pp", "exposure_rf", "exposure_rf_10pp",
          "exposure_rf_relative", "exposure_rf_relative_10pp",
          "post_nov2022", "may2024_age_backcast"
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

plot_event <- function(event_table, specification, outcome) {
  limits <- if (grepl("parados", outcome)) c(-0.05, 0.15) else c(-0.20, 0.20)
  plot <- ggplot(event_table, aes(event_time, estimate)) +
    geom_hline(yintercept = 0, color = "grey55", linewidth = 0.35) +
    geom_vline(xintercept = 0, color = "grey55", linetype = "dashed", linewidth = 0.35) +
    geom_ribbon(
      aes(ymin = ci_low, ymax = ci_high),
      fill = "#56B4E9", alpha = 0.24, color = NA
    ) +
    geom_line(color = "#08519C", linewidth = 0.75) +
    geom_point(color = "#08519C", size = 1.35) +
    scale_x_continuous(
      limits = c(event_min, event_max),
      breaks = seq(-20, 40, by = 10)
    ) +
    coord_cartesian(ylim = limits) +
    labs(
      x = "Months relative to November 2022",
      y = "Marginal effect"
    ) +
    theme_minimal(base_size = 10.5) +
    theme(
      panel.grid.minor = element_blank(),
      axis.line = element_line(color = "grey35", linewidth = 0.35),
      axis.ticks = element_line(color = "grey35", linewidth = 0.35),
      plot.title = element_blank()
    )

  ggsave(
    file.path(figures_dir, paste0(
      "contdid_event_", safe_name(specification), "_", outcome, ".png"
    )),
    plot,
    width = 7.0,
    height = 4.4,
    dpi = 320
  )
}

support_by_cno1 <- function(df, dose_var = "exposure_10pp") {
  df |>
    distinct(cno4, cno1d, dose = .data[[dose_var]]) |>
    group_by(cno1d) |>
    summarise(
      occupations = n(),
      positive_occupations = sum(dose > 0, na.rm = TRUE),
      zero_occupations = sum(dose == 0, na.rm = TRUE),
      mean_dose = mean(dose, na.rm = TRUE),
      sd_dose = sd(dose, na.rm = TRUE),
      min_dose = min(dose, na.rm = TRUE),
      max_dose = max(dose, na.rm = TRUE),
      .groups = "drop"
    ) |>
    mutate(
      supported = positive_occupations >= min_positive & zero_occupations >= min_zero,
      positive_weight = if_else(
        supported,
        positive_occupations / sum(positive_occupations[supported]),
        0
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
  write_covariance(extracted$covariance, event$event_time, specification, outcome)
  plot_event(event, specification, outcome)

  list(event = event, average = average, phases = phases, covariance = extracted$covariance)
}

fit_stratified_event <- function(df, outcome, specification, dose_var = "exposure_10pp") {
  support <- support_by_cno1(df, dose_var)
  supported_groups <- support |>
    filter(supported) |>
    pull(cno1d)

  if (length(supported_groups) == 0L) {
    stop("No CNO1 family satisfies the support rule.")
  }

  fits <- list()
  family_diagnostics <- list()
  for (family in supported_groups) {
    family_df <- df |> filter(cno1d == family)
    family_data <- make_contdid_data(family_df, outcome, dose_var) |>
      group_by(id) |>
      filter(n_distinct(ym_index) == n_distinct(family_df$ym_index)) |>
      ungroup()

    message("  CNO1 ", family, ": ", outcome)
    object <- cont_did_fixed(
      family_data,
      aggregation = "eventstudy",
      target_parameter = "slope",
      cband = FALSE,
      biters = biters
    )
    extracted <- extract_event(object)
    family_weight <- support$positive_weight[support$cno1d == family]
    fits[[as.character(family)]] <- list(
      event = extracted$table,
      covariance = extracted$covariance,
      weight = family_weight
    )
    family_average <- average_post(extracted$table, extracted$covariance)
    family_diagnostics[[as.character(family)]] <- family_average |>
      mutate(
        cno1d = family,
        positive_weight = family_weight,
        positive_occupations = support$positive_occupations[support$cno1d == family],
        zero_occupations = support$zero_occupations[support$cno1d == family],
        units = n_distinct(family_data$id),
        .before = 1
      )
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
  average <- average_post(event, aggregate_covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      dose_var = dose_var,
      supported_cno1_groups = length(fits),
      supported_positive_occupations = sum(
        support$positive_occupations[support$supported]
      ),
      supported_zero_occupations = sum(support$zero_occupations[support$supported]),
      covariance_source = "weighted sum of disjoint-family IF covariance matrices",
      biters = biters,
      .before = 1
    )
  phases <- phase_average(event, aggregate_covariance) |>
    mutate(
      specification = specification,
      outcome = outcome,
      dose_var = dose_var,
      supported_cno1_groups = length(fits),
      supported_positive_occupations = sum(
        support$positive_occupations[support$supported]
      ),
      supported_zero_occupations = sum(support$zero_occupations[support$supported]),
      covariance_source = "weighted sum of disjoint-family IF covariance matrices",
      biters = biters,
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
  write_covariance(aggregate_covariance, common_time, specification, outcome)
  plot_event(event, specification, outcome)

  list(event = event, average = average, phases = phases, covariance = aggregate_covariance)
}

control_based_adjustment <- function(df, outcome, dose_var = "exposure_10pp") {
  support <- support_by_cno1(df, dose_var)
  supported_groups <- support |>
    filter(supported) |>
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

  message("CNO1-stratified ContDID: ", outcome)
  stratified <- fit_stratified_event(
    df, outcome, "cno1_stratified", "exposure_10pp"
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
support <- support_by_cno1(total)
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
