#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  required_packages <- c("arrow", "pdftools")
  missing_packages <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing_packages) > 0) {
    stop(
      "Missing required R packages: ",
      paste(missing_packages, collapse = ", "),
      ". Install them before running this script.",
      call. = FALSE
    )
  }
})

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || is.na(x)) y else x
}

pad_code <- function(x, width) {
  x <- as.character(x)
  x <- trimws(x)
  x <- ifelse(grepl("^[0-9]+$", x), x, NA_character_)
  ifelse(is.na(x), NA_character_, sprintf(paste0("%0", width, "d"), as.integer(x)))
}

command_args <- commandArgs(trailingOnly = FALSE)
file_arg <- command_args[grepl("^--file=", command_args)]
script_dir <- if (length(file_arg) > 0) {
  dirname(normalizePath(sub("^--file=", "", file_arg[[1]]), winslash = "/", mustWork = TRUE))
} else {
  normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

project_root <- normalizePath(file.path(script_dir, ".."), winslash = "/", mustWork = TRUE)
default_output_path <- file.path(project_root, "data", "tmp", "cno4_anthropic_nearest_lookup.parquet")

args <- commandArgs(trailingOnly = TRUE)
output_path <- if (length(args) >= 1) args[[1]] else default_output_path

normalize_text <- function(x) {
  x <- enc2utf8(x)
  x <- gsub("\u00ad", "", x, fixed = TRUE)
  x <- gsub("[[:space:]]+", " ", x)
  trimws(x)
}

repair_pdf_text <- function(x) {
  x <- normalize_text(x)
  x <- gsub("([[:alnum:]])- ([[:alnum:]])", "\\1\\2", x, perl = TRUE)
  x <- gsub("\\s+([,.;:])", "\\1", x, perl = TRUE)
  normalize_text(x)
}

extract_pdf_lines <- function(pdf_path) {
  pages <- pdftools::pdf_text(pdf_path)
  lines <- unlist(strsplit(pages, "\n", fixed = TRUE), use.names = FALSE)
  lines <- vapply(lines, normalize_text, character(1))
  lines[nzchar(lines)]
}

parse_heading_map <- function(lines, pattern) {
  stop_pattern <- "^(\\d{1,4}|[A-Z])\\s+"
  results <- list()
  i <- 1L
  n <- length(lines)

  while (i <= n) {
    current <- lines[[i]]
    match <- regexec(pattern, current, perl = TRUE)
    pieces <- regmatches(current, match)[[1]]

    if (length(pieces) == 0) {
      i <- i + 1L
      next
    }

    code <- pieces[[2]]
    title_parts <- pieces[[3]]
    i <- i + 1L

    while (i <= n && !grepl(stop_pattern, lines[[i]], perl = TRUE)) {
      title_parts <- c(title_parts, lines[[i]])
      i <- i + 1L
    }

    results[[code]] <- repair_pdf_text(paste(title_parts, collapse = " "))
  }

  data.frame(
    code = names(results),
    title = unname(unlist(results, use.names = FALSE)),
    stringsAsFactors = FALSE
  )
}

read_csv_strict <- function(path) {
  utils::read.csv(path, stringsAsFactors = FALSE, check.names = FALSE, encoding = "UTF-8")
}

build_lookup <- function(project_root) {
  nearest_path <- file.path(project_root, "data", "processed", "spanish_occupation_matches_cosine_nearest.csv")
  sepe_path <- file.path(project_root, "data", "processed", "sepe_cno4_monthly_ai_exposure.csv")
  cno1_path <- file.path(project_root, "data", "processed", "spanish_occupation_exposure.csv")
  pdf_path <- file.path(project_root, "data", "raw", "ine", "cno11_notas.pdf")

  required_paths <- c(nearest_path, sepe_path, cno1_path, pdf_path)
  missing_paths <- required_paths[!file.exists(required_paths)]
  if (length(missing_paths) > 0) {
    stop("Missing required input files:\n", paste(missing_paths, collapse = "\n"), call. = FALSE)
  }

  nearest <- read_csv_strict(nearest_path)
  sepe <- read_csv_strict(sepe_path)
  cno1 <- read_csv_strict(cno1_path)

  nearest$CNO4 <- pad_code(nearest$CNO4, 4)
  nearest$CNO2 <- pad_code(nearest$CNO2, 2)
  nearest$OCUP1 <- as.character(nearest$OCUP1)

  exposure <- unique(sepe[c("cno4", "occupation_title", "observed_exposure_cosine_nearest")])
  names(exposure) <- c("cno4", "cno4_title_sepe", "observed_exposure_cosine_nearest")
  exposure$cno4 <- pad_code(exposure$cno4, 4)

  cno1_map <- unique(cno1[c("OCUP1", "occupation_title")])
  names(cno1_map) <- c("cno1", "cno1_title")
  cno1_map$cno1 <- as.character(cno1_map$cno1)

  lines <- extract_pdf_lines(pdf_path)
  cno2_map <- parse_heading_map(lines, "^(\\d{2})\\s+(.+)$")
  names(cno2_map) <- c("cno2", "cno2_title")
  cno2_map$cno2 <- pad_code(cno2_map$cno2, 2)
  cno2_map <- cno2_map[!duplicated(cno2_map$cno2), ]

  out <- unique(nearest[c(
    "CNO4",
    "CNO2",
    "OCUP1",
    "spanish_title",
    "anthropic_occ_code",
    "anthropic_title",
    "anthropic_observed_exposure",
    "cosine_similarity"
  )])

  names(out) <- c(
    "cno4",
    "cno2",
    "cno1",
    "cno4_title_match",
    "anthropic_occ_code",
    "anthropic_title",
    "anthropic_observed_exposure",
    "cosine_similarity"
  )

  out <- merge(out, exposure, by = "cno4", all.x = TRUE, sort = FALSE)
  out <- merge(out, cno2_map, by = "cno2", all.x = TRUE, sort = FALSE)
  out <- merge(out, cno1_map, by = "cno1", all.x = TRUE, sort = FALSE)

  out$cno4_title <- ifelse(
    is.na(out$cno4_title_sepe) | !nzchar(out$cno4_title_sepe),
    out$cno4_title_match,
    out$cno4_title_sepe
  )

  out$cno2_title <- ifelse(
    is.na(out$cno2_title) | !nzchar(out$cno2_title),
    paste("CNO2", out$cno2),
    out$cno2_title
  )

  out$cno1_title <- ifelse(
    is.na(out$cno1_title) | !nzchar(out$cno1_title),
    paste("CNO1", out$cno1),
    out$cno1_title
  )

  out <- out[c(
    "cno4",
    "cno4_title",
    "observed_exposure_cosine_nearest",
    "anthropic_occ_code",
    "anthropic_title",
    "anthropic_observed_exposure",
    "cosine_similarity",
    "cno2",
    "cno2_title",
    "cno1",
    "cno1_title"
  )]

  out <- out[order(out$cno4), ]
  rownames(out) <- NULL
  out
}

dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
lookup <- build_lookup(project_root)
arrow::write_parquet(lookup, output_path)

message("Wrote parquet to: ", output_path)
message("Rows: ", nrow(lookup))
