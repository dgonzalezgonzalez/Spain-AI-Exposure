# Restore the exact recorded package versions into the replication directory.
args <- commandArgs(trailingOnly = FALSE)
file <- sub('^--file=', '', args[grepl('^--file=', args)])
root <- dirname(dirname(normalizePath(file, winslash = '/', mustWork = TRUE)))
library_dir <- file.path(root, '.r_libs')
dir.create(library_dir, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(library_dir, .libPaths()))
options(repos = c(CRAN = 'https://cloud.r-project.org'))
if (!requireNamespace('renv', quietly = TRUE)) install.packages('renv', lib = library_dir)
lock <- renv::lockfile_read(file.path(root, 'renv.lock'))
missing <- names(Filter(function(record) {
  if (!requireNamespace(record$Package, quietly = TRUE)) return(TRUE)
  current <- packageDescription(record$Package)
  if (!identical(current$Version, record$Version)) return(TRUE)
  if (!is.null(record$RemoteSha) && !identical(current$RemoteSha, record$RemoteSha)) return(TRUE)
  FALSE
}, lock$Packages))
if (length(missing)) {
  renv::restore(project = root, lockfile = file.path(root, 'renv.lock'),
                library = library_dir, packages = missing, prompt = FALSE)
}
cat('R dependencies restored to', library_dir, '\n')
