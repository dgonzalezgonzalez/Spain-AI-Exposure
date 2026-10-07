version 17
clear all
set more off
set maxvar 10000
local script_file `"`c(filename)'"'
local script_dir "`c(pwd)'"
if `"`script_file'"' != "" {
    local last_slash = max(strrpos("`script_file'", "/"), strrpos("`script_file'", "\"))
    if `last_slash' > 0 local script_dir = substr("`script_file'", 1, `last_slash' - 1)
}
local script_dir : subinstr local script_dir "\" "/", all

global IN   "`script_dir'/data/prepared"
global TAB  "`script_dir'/intermediate"
global FIG  "`script_dir'/intermediate"
global LOG  "`script_dir'/logs"

global EVENT_MONTH tm(2022m11)
global ES_MIN -21
global ES_MAX 40
global HIGH_CUTOFF 0.1169
global SDID_REPS 500
global V1_SDID_REPS : environment V1_SDID_REPS
if "$V1_SDID_REPS" != "" global SDID_REPS $V1_SDID_REPS
global SEED 20260728

foreach package in ftools reghdfe sdid sdid_event {
    which `package'
}
capture log close
log using "$LOG/sdid.log", replace text
do "`script_dir'/lib/estimators.do"
display as result "Running expanded-donor synthetic DID"
load_v1_panel using "$IN/est_total_cno4.csv"

* Preferred SDID: upper-tail exposure versus a synthetic combination of every
* occupation at or below the cutoff, with native CNO1-by-month adjustment.
foreach outcome in ln_parados ln_contratos {
    load_v1_panel using "$IN/est_total_cno4.csv"
    make_cno1_month_basis
    local cno1_month_covariates `r(covariates)'
    run_sdid_average_paths_v1, spec("expanded_donor_cno1_month") ///
        outcome(`outcome') covariates("`cno1_month_covariates'") pathonly
    run_sdid_event_v1, spec("expanded_donor_cno1_month") ///
        outcome(`outcome') covariates("`cno1_month_covariates'")
    foreach phase in adjustment later {
        run_sdid_phase_v1, spec("expanded_donor_cno1_month") ///
            outcome(`outcome') phase("`phase'") projectcno1
    }
}

foreach outcome in ln_parados ln_contratos {
    load_v1_panel using "$IN/est_total_cno4.csv"
    replace sdid_high = exposure_nearest > 0.2 if !missing(exposure_nearest)
    replace sdid_donor = exposure_nearest == 0 if !missing(exposure_nearest)
    keep if sdid_high == 1 | sdid_donor == 1
    replace sdid_treatment = sdid_high * (event_time >= 0)
    foreach phase in adjustment later {
        run_sdid_phase_v1, spec("high020_zeroonly_cno1_month") outcome(`outcome') phase("`phase'") autocovariates
    }
}
log close
