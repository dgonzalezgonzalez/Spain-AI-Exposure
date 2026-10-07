* Paired exposure regressions and matching Table 2 event-study diagnostics.
* Usage: do job_tier_mediation.do "panel.csv" "output_dir" "ado/plus"
version 17
args panel output plus
clear all
set more off
set maxvar 10000
if "`plus'" != "" sysdir set PLUS "`plus'"
cd "`output'"
capture log close
log using "job_tier_mediation_results.log", replace text
import delimited using "`panel'", clear varnames(1) bindquote(strict) encoding("UTF-8")
foreach v in ym_stata ln_parados ln_contratos exposure_10pp jev_tier {
    capture destring `v', replace force
}
egen long cno4_id = group(cno4)
egen long cno1_ym = group(cno1d ym_stata)
egen long tier_ym = group(jev_tier ym_stata)
gen int event_time = ym_stata - 754
keep if inrange(event_time, -21, 40)
isid cno4_id ym_stata
assert inlist(jev_tier, 1, 2, 3)
bysort cno4_id: assert jev_tier == jev_tier[1]
gen double dose_adjustment = exposure_10pp * inrange(event_time, 0, 24)
gen double dose_later = exposure_10pp * inrange(event_time, 25, 40)
foreach tier in 1 2 {
    gen byte tier`tier'_adjustment = (jev_tier == `tier') * inrange(event_time, 0, 24)
    gen byte tier`tier'_later = (jev_tier == `tier') * inrange(event_time, 25, 40)
}
local all
local pre
forvalues k = -21/40 {
    if `k' != -1 {
        if `k' < 0 local suffix "m`=abs(`k')'"
        else local suffix "p`k'"
        gen double es_`suffix' = exposure_10pp * (event_time == `k')
        local all `all' es_`suffix'
        if `k' < -1 local pre `pre' es_`suffix'
    }
}
tempfile estimates diagnostics
postfile R str16 outcome str16 specification str20 term double estimate se p equality_p long observations clusters using `estimates', replace
postfile P str16 outcome str16 specification double F_stat df_num df_den p_value long observations clusters using `diagnostics', replace
foreach y in ln_parados ln_contratos {
    * All comparisons use the baseline's outcome-specific estimation sample.
    quietly reghdfe `y' dose_adjustment dose_later, absorb(cno4_id cno1_ym) vce(cluster cno4_id)
    gen byte common_sample = e(sample)
    foreach spec in baseline phase_controls month_fe {
        local controls
        local absorb cno4_id cno1_ym
        if "`spec'" == "phase_controls" local controls tier1_adjustment tier1_later tier2_adjustment tier2_later
        if "`spec'" == "month_fe" local absorb cno4_id cno1_ym tier_ym
        reghdfe `y' dose_adjustment dose_later `controls' if common_sample, absorb(`absorb') vce(cluster cno4_id)
        assert e(N) == 31122 if "`y'" == "ln_parados"
        assert e(N) == 30786 if "`y'" == "ln_contratos"
        local N = e(N)
        local G = e(N_clust)
        test dose_adjustment = dose_later
        local eq = r(p)
        foreach term in dose_adjustment dose_later {
            lincom `term'
            post R ("`y'") ("`spec'") ("`term'") (r(estimate)) (r(se)) (r(p)) (`eq') (`N') (`G')
        }
        * Same 61 exposure event terms, October 2022 reference, and 20
        * restrictions (event times -21 through -2) as Table 2.
        reghdfe `y' `all' `controls' if common_sample, absorb(`absorb') vce(cluster cno4_id)
        test `pre'
        post P ("`y'") ("`spec'") (r(F)) (r(df)) (r(df_r)) (r(p)) (e(N)) (e(N_clust))
    }
    drop common_sample
}
postclose R
postclose P
use `estimates', clear
export delimited using "job_tier_mediation_estimates.csv", replace
use `diagnostics', clear
export delimited using "job_tier_mediation_pretrends.csv", replace
log close
