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
log using "$LOG/jev.log", replace text
do "`script_dir'/lib/estimators.do"
do "`script_dir'/lib/job_tiers.do"
global V1_OCCUPATION_MODEL "jev"
    local occupation_model "$V1_OCCUPATION_MODEL"
    display as result "Producing `occupation_model' O.D. robustness outputs"
    if "$V1_TIERS_ONLY" != "1" {
    * Reproduce O.D.1's six columns: benchmark, preferred, preferred without 2021.
    load_v1_panel using "$IN/est_total_cno4.csv"
    gen byte sample_from_2022 = ym_stata >= tm(2022m1)
    foreach outcome in ln_parados ln_contratos {
        run_phase_effects, spec("benchmark_twfe") outcome(`outcome') ///
            absorb("cno4_id ym_id")
        run_phase_effects, spec("preferred_cno1_month") outcome(`outcome') ///
            absorb("cno4_id cno1_ym")
        run_phase_effects, spec("preferred_cno1_month_no2021") ///
            outcome(`outcome') absorb("cno4_id cno1_ym") ///
            samplevar(sample_from_2022)
        run_twfe, spec("benchmark_twfe") outcome(`outcome') ///
            absorb("cno4_id ym_id")
        run_twfe, spec("preferred_cno1_month") outcome(`outcome') ///
            absorb("cno4_id cno1_ym")
        run_twfe, spec("preferred_cno1_month_no2021") outcome(`outcome') ///
            absorb("cno4_id cno1_ym") samplevar(sample_from_2022)
    }

    foreach measure in nearest weighted direct {
        load_v1_panel using "$IN/est_total_cno4_`occupation_model'.csv"
        gen byte sample_from_2022 = ym_stata >= tm(2022m1)
        foreach outcome in ln_parados ln_contratos {
            run_phase_effects, spec("`occupation_model'_`measure'_benchmark") ///
                outcome(`outcome') dosevar(exposure_`occupation_model'_`measure'_10pp) ///
                absorb("cno4_id ym_id")
            run_phase_effects, spec("`occupation_model'_`measure'_cno1_month") ///
                outcome(`outcome') dosevar(exposure_`occupation_model'_`measure'_10pp) ///
                absorb("cno4_id cno1_ym")
            run_phase_effects, spec("`occupation_model'_`measure'_cno1_month_no2021") ///
                outcome(`outcome') dosevar(exposure_`occupation_model'_`measure'_10pp) ///
                absorb("cno4_id cno1_ym") samplevar(sample_from_2022)
            run_twfe, spec("`occupation_model'_`measure'_benchmark") outcome(`outcome') ///
                dosevar(exposure_`occupation_model'_`measure'_10pp) absorb("cno4_id ym_id")
            run_twfe, spec("`occupation_model'_`measure'_cno1_month") outcome(`outcome') ///
                dosevar(exposure_`occupation_model'_`measure'_10pp) ///
                absorb("cno4_id cno1_ym")
            run_twfe, spec("`occupation_model'_`measure'_cno1_month_no2021") ///
                outcome(`outcome') dosevar(exposure_`occupation_model'_`measure'_10pp) ///
                absorb("cno4_id cno1_ym") samplevar(sample_from_2022)
        }
    }

    }
    produce_job_tier_outputs, model("`occupation_model'")
log close
