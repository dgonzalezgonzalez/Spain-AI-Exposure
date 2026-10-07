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
log using "$LOG/estimates.log", replace text
do "`script_dir'/lib/estimators.do"
load_v1_panel using "$IN/est_total_cno4.csv"
export_support, level(cno1d)
export_support, level(cno2)
foreach outcome in ln_parados ln_contratos {
    run_twfe, spec("benchmark_twfe") outcome(`outcome') absorb("cno4_id ym_id")
    run_twfe, spec("preferred_cno1_month") outcome(`outcome') absorb("cno4_id cno1_ym")
    run_twfe, spec("cosine_weighted_cno1_month") outcome(`outcome') dosevar(exposure_weighted_10pp) absorb("cno4_id cno1_ym")
    run_twfe, spec("benchmark_cosine_weighted") outcome(`outcome') dosevar(exposure_weighted_10pp) absorb("cno4_id ym_id")
}
foreach outcome in ln_parados_p1 ln_contratos_p1 {
    run_twfe, spec("benchmark_log_plus_one") outcome(`outcome') absorb("cno4_id ym_id")
    run_twfe, spec("log_plus_one_cno1_month") outcome(`outcome') absorb("cno4_id cno1_ym")
}
levelsof cno1d, local(cno1_groups)
tempfile leaveout_source
save `leaveout_source', replace
foreach group of local cno1_groups {
    use `leaveout_source', clear
    keep if cno1d != `group'
    foreach outcome in ln_parados ln_contratos {
        run_long_difference, spec("leaveout_cno1_`group'") outcome(`outcome') unitvar(unit_id) familyfe(cno1d)
    }
}
foreach dimension in age3 gender {
    load_v1_panel using "$IN/est_`dimension'_cno4.csv"
    levelsof `dimension', local(subgroups)
    tempfile subgroup_source
    save `subgroup_source', replace
    foreach subgroup of local subgroups {
        use `subgroup_source', clear
        keep if `dimension' == "`subgroup'"
        local tag = lower(subinstr(subinstr(subinstr("`subgroup'", " ", "_", .), "<", "lt", .), ">", "gt", .))
        local prefix = cond("`dimension'"=="age3", "age", "gender")
        foreach outcome in ln_parados ln_contratos {
            run_twfe, spec("`prefix'_`tag'_benchmark") outcome(`outcome') absorb("unit_id ym_id")
            run_twfe, spec("`prefix'_`tag'_cno1_month") outcome(`outcome') absorb("unit_id cno1_ym")
        }
    }
}
produce_pooled_age_tests
produce_phase_outputs
produce_feminization_analysis
produce_refinement_outputs
log close
