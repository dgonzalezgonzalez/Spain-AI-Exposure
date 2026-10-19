version 17
clear all
set more off
set maxvar 10000
local script_dir "`c(pwd)'"
global IN "`script_dir'/data/prepared"
global TAB "`script_dir'/intermediate"
global FIG "$TAB"
global LOG "`script_dir'/logs"
global EVENT_MONTH tm(2022m11)
global ES_MIN -21
global ES_MAX 40
global HIGH_CUTOFF 0.1169
global SEED 20260728
capture log close
log using "$LOG/edgecases.log", replace text
do "`script_dir'/lib/estimators.do"
foreach mapping in baseline edgecases {
    if "`mapping'" == "baseline" {
        load_v1_panel using "$IN/est_total_cno4.csv"
        local dose exposure_10pp
    }
    else {
        load_v1_panel using "$IN/est_total_cno4_edgecases.csv"
        local dose exposure_edgecases_10pp
        assert !missing(`dose')
    }
    gen byte sample_no2021 = ym_stata >= tm(2022m1)
    foreach outcome in ln_parados ln_contratos {
        foreach suffix in benchmark cno1_month cno1_month_no2021 {
            local fixed "cno4_id cno1_ym"
            if "`suffix'" == "benchmark" local fixed "cno4_id ym_id"
            local restrict
            if "`suffix'" == "cno1_month_no2021" local restrict "samplevar(sample_no2021)"
            local specification "edge_`mapping'_`suffix'"
            run_phase_effects, spec("`specification'") outcome(`outcome') ///
                dosevar(`dose') absorb("`fixed'") `restrict'
            run_twfe, spec("`specification'") outcome(`outcome') ///
                dosevar(`dose') absorb("`fixed'") `restrict'
        }
    }
}
log close
