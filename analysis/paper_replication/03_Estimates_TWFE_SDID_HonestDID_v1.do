version 17
clear all
set more off
set maxvar 10000

********************************************************************************
* Estimates_TWFE_SDID_HonestDID_v1.do
*
* Purpose
* -------
* This is the Stata production file for version 1 of the empirical analysis.
* The preferred design is a continuous-treatment TWFE event study that compares
* CNO4 occupations within CNO1 families in every calendar month.
*
* Inputs
* ------
* 01_Preparation_v1.ipynb writes standardized panels to:
*     data/prepared/
* The age panel includes audited May 2024 backcasts from June levels and
* June-over-May rates; unresolved cells remain missing and are documented in
* intermediate/sepe_may2024_age_backcast_missingness_v1.csv.
*
* Outputs
* -------
* Estimator outputs are written to intermediate/ and logs to logs/. The final
* publication files are created by 05_Output_tuning_v1.ipynb.
*
* Shock and event-time convention
* -------------------------------
* November 2022 is event time 0, December 2022 is event time 1, and
* October 2022 (event time -1) is the omitted reference month.
*
* Specifications
* --------------
* SPEC 1 (preferred):
*   y_jt = alpha_j + lambda_{CNO1(j),t}
*          + sum_{k != -1} beta_k Exposure10_j 1[event_time=k] + error_jt
*   Fixed effects: CNO4 and CNO1 x year-month.
*   Inference: standard errors clustered by CNO4.
*
* SPEC 2 (unconditional benchmark):
*   Fixed effects: CNO4 and year-month.
*
* Synthetic difference-in-differences:
*   Treated occupations have nearest-neighbor exposure > 0.1169.
*   Every occupation at or below 0.1169 is retained in the donor pool,
*   including zero- and middle-exposure occupations.
*   The preferred specification adjusts for CNO1 x year-month indicators
*   within the SDID estimation.
********************************************************************************

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
global V1_SMOKE : environment V1_SMOKE
global V1_SDID_EVENT_ONLY : environment V1_SDID_EVENT_ONLY
global V1_SDID_EVENT_SKIP_TOTAL : environment V1_SDID_EVENT_SKIP_TOTAL
global V1_AGE_TWFE_ONLY : environment V1_AGE_TWFE_ONLY
global V1_MAIN_TABLE_ONLY : environment V1_MAIN_TABLE_ONLY
global V1_LONGDIFF_ONLY : environment V1_LONGDIFF_ONLY
global V1_JEV_OD_ONLY : environment V1_JEV_OD_ONLY
global V1_HETERO_TWFE_ONLY : environment V1_HETERO_TWFE_ONLY
global V1_FEMINIZATION_ONLY : environment V1_FEMINIZATION_ONLY
global V1_PHASE_ONLY : environment V1_PHASE_ONLY
global V1_ROBUST_PRETREND_ONLY : environment V1_ROBUST_PRETREND_ONLY
global V1_PROVINCE_ONLY : environment V1_PROVINCE_ONLY
global V1_SDID_PHASE_ONLY : environment V1_SDID_PHASE_ONLY
global V1_SDID_PHASE_JOB : environment V1_SDID_PHASE_JOB
global V1_SDID_EVENT_JOB : environment V1_SDID_EVENT_JOB
global V1_SDID_PATH_ONLY : environment V1_SDID_PATH_ONLY
global V1_SDID_EVENT_GRAPH_ONLY : environment V1_SDID_EVENT_GRAPH_ONLY
global V1_SDID_JOB_SPEC : environment V1_SDID_JOB_SPEC
global V1_SDID_JOB_OUTCOME : environment V1_SDID_JOB_OUTCOME
global V1_SDID_JOB_PHASE : environment V1_SDID_JOB_PHASE

capture mkdir "$TAB"
capture mkdir "$FIG"
capture mkdir "$FIG/paper_clean"
capture mkdir "$LOG"

capture log close
if "$V1_LONGDIFF_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_longdiff_only.log", replace text
}
else if "$V1_JEV_OD_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_jev_od_only.log", replace text
}
else if "$V1_MAIN_TABLE_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_main_table_only.log", replace text
}
else if "$V1_HETERO_TWFE_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_heterogeneity_twfe_only.log", replace text
}
else if "$V1_FEMINIZATION_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_feminization_only.log", replace text
}
else if "$V1_PHASE_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_phase_only.log", replace text
}
else if "$V1_ROBUST_PRETREND_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_robust_pretrends.log", replace text
}
else if "$V1_PROVINCE_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_province_only.log", replace text
}
else if "$V1_SDID_PHASE_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_sdid_phase_only.log", replace text
}
else if "$V1_SDID_PHASE_JOB" == "1" {
    log using "$LOG/sdid_phase_job_${V1_SDID_JOB_SPEC}_${V1_SDID_JOB_OUTCOME}_${V1_SDID_JOB_PHASE}.log", replace text
}
else if "$V1_SDID_EVENT_JOB" == "1" {
    log using "$LOG/sdid_event_job_${V1_SDID_JOB_OUTCOME}.log", replace text
}
else if "$V1_SDID_PATH_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_sdid_path_only.log", replace text
}
else if "$V1_SMOKE" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_smoke.log", replace text
}
else if "$V1_SDID_EVENT_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_event_only.log", replace text
}
else if "$V1_AGE_TWFE_ONLY" == "1" {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1_age_twfe_only.log", replace text
}
else {
    log using "$LOG/Estimates_TWFE_SDID_HonestDID_v1.log", replace text
}

********************************************************************************
* 0. Required packages
********************************************************************************

local required_packages "ftools reghdfe distinct sdid sdid_event honestdid"
if "$V1_JEV_OD_ONLY" == "1" local required_packages "ftools reghdfe"
foreach package of local required_packages {
    capture which `package'
    if _rc {
        display as error "Required package `package' is not installed."
        display as error "Install it before running this production file."
        exit 499
    }
}

********************************************************************************
* 1. Shared data and event-study helpers
********************************************************************************

capture program drop load_v1_panel
program define load_v1_panel
    syntax using/

    import delimited using "`using'", clear varnames(1) bindquote(strict) encoding("UTF-8")

    foreach v in ym_stata ym_index parados contratos contratos_12m ///
        ln_parados ln_contratos ln_contratos_12m ///
        ln_parados_p1 ln_contratos_p1 exposure_nearest exposure_10pp ///
        exposure_weighted exposure_weighted_10pp exposure_rf exposure_rf_10pp ///
        exposure_rf_relative exposure_rf_relative_10pp post_nov2022 ///
        exposure_jev_nearest exposure_jev_nearest_10pp ///
        exposure_jev_weighted exposure_jev_weighted_10pp ///
        exposure_jev_direct exposure_jev_direct_10pp ///
        may2024_age_backcast may2024_province_backcast female ///
        feminization_2017_2019 feminization_2021q1_2022q3 ///
        feminization_change feminization_10pp_centered ///
        female_share_parados female_share_contratos ///
        log_gender_ratio_parados log_gender_ratio_contratos ///
        parados_female parados_male contratos_female contratos_male {
        capture destring `v', replace force
    }

    capture confirm string variable cno4
    if _rc tostring cno4, replace format("%04.0f")
    replace cno4 = string(real(cno4), "%04.0f") if strlen(cno4) < 4

    capture confirm string variable cno1d
    if !_rc destring cno1d, replace force
    capture confirm string variable cno2
    if !_rc destring cno2, replace force

    egen long unit_id = group(unit)
    egen long cno4_id = group(cno4)
    gen str3 cno3 = substr(cno4, 1, 3)
    egen long cno3_id = group(cno3)
    egen long cno2_id = group(cno2)
    egen long ym_id = group(ym_stata)
    egen long cno1_ym = group(cno1d ym_stata)
    egen long cno2_ym = group(cno2 ym_stata)

    capture confirm variable province
    if !_rc {
        egen long province_id = group(province)
        egen long province_ym = group(province ym_stata)
    }

    capture confirm variable gender
    if !_rc egen long cno1_gender_ym = group(cno1d gender ym_stata)

    capture confirm variable age3
    if !_rc {
        egen long age_id = group(age3)
        egen long age_cno1_ym = group(age3 cno1d ym_stata)
    }

    capture drop event_time
    gen int event_time = ym_stata - $EVENT_MONTH
    gen byte post = ym_stata >= $EVENT_MONTH
    gen byte post_effect = event_time >= 1

    * Expanded-donor SDID design. No middle-exposure occupation is removed.
    foreach variable in sdid_high sdid_donor sdid_treatment {
        capture drop `variable'
    }
    gen byte sdid_high = exposure_nearest > $HIGH_CUTOFF if !missing(exposure_nearest)
    gen byte sdid_donor = exposure_nearest <= $HIGH_CUTOFF if !missing(exposure_nearest)
    gen byte sdid_treatment = sdid_high * post

    format ym_stata %tm
end


capture program drop run_phase_effects
program define run_phase_effects
    syntax, SPEC(string) OUTCOME(name) ABSORB(string) ///
        [DOSEVAR(name) CLUSTERVAR(name) SAMPLEVAR(name)]

    if "`dosevar'" == "" local dosevar exposure_10pp
    if "`clustervar'" == "" local clustervar cno4_id

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
        keep if !missing(`outcome', `dosevar', `clustervar')

        gen double dose_adjustment = `dosevar' * inrange(event_time, 0, 24)
        gen double dose_later = `dosevar' * inrange(event_time, 25, 40)

        reghdfe `outcome' dose_adjustment dose_later, ///
            absorb(`absorb') vce(cluster `clustervar')

        local observations = e(N)
        local clusters = e(N_clust)
        test dose_adjustment = dose_later
        local equality_p = r(p)

        tempfile phase_results
        postfile P str48 specification str32 outcome str32 dosevar ///
            str16 phase int event_start event_end ///
            double estimate se ci_low ci_high effect_percent equality_p ///
            long observations clusters using `phase_results', replace

        foreach phase in adjustment later {
            if "`phase'" == "adjustment" {
                local variable dose_adjustment
                local start 0
                local end 24
            }
            else {
                local variable dose_later
                local start 25
                local end 40
            }
            lincom `variable'
            post P ("`spec'") ("`outcome'") ("`dosevar'") ///
                ("`phase'") (`start') (`end') ///
                (r(estimate)) (r(se)) (r(lb)) (r(ub)) ///
                (100*r(estimate)) (`equality_p') ///
                (`observations') (`clusters')
        }
        postclose P

        use `phase_results', clear
        export delimited using "$TAB/twfe_phase_`spec'_`outcome'.csv", replace
    restore
end


capture program drop make_continuous_event_terms
program define make_continuous_event_terms
    syntax, DOSEVAR(name)

    capture drop es_*
    forvalues k = $ES_MIN/$ES_MAX {
        if `k' < 0 local suffix "m`=abs(`k')'"
        else local suffix "p`k'"

        if `k' != -1 {
            gen double es_`suffix' = `dosevar' * (event_time == `k')
            label variable es_`suffix' "`dosevar' x event time `k'"
        }
    }
end


capture program drop event_varlists
program define event_varlists, rclass
    local all
    local post
    local pre_full
    local pre_recent

    forvalues k = $ES_MIN/$ES_MAX {
        if `k' < 0 local suffix "m`=abs(`k')'"
        else local suffix "p`k'"

        if `k' != -1 {
            local all `all' es_`suffix'
            if inrange(`k', 1, $ES_MAX) local post `post' es_`suffix'
            if inrange(`k', $ES_MIN, -2) local pre_full `pre_full' es_`suffix'
            if inrange(`k', -10, -2) local pre_recent `pre_recent' es_`suffix'
        }
    }

    return local all "`all'"
    return local post "`post'"
    return local pre_full "`pre_full'"
    return local pre_recent "`pre_recent'"
end


capture program drop export_covariance
program define export_covariance
    syntax, SPEC(string) OUTCOME(string)

    tempfile active_data
    save `active_data', replace

    matrix V_event = e(V)
    event_varlists
    local all `r(all)'
    local n : word count `all'

    local declarations
    forvalues j = 1/`n' {
        local declarations `declarations' double cov_`j'
    }

    tempfile covariance
    postfile C str40 term int event_time `declarations' using `covariance', replace

    local i = 0
    forvalues k = $ES_MIN/$ES_MAX {
        if `k' != -1 {
            local ++i
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"

            local row
            forvalues j = 1/`n' {
                local value = el(V_event, `i', `j')
                local row `row' (`value')
            }
            post C ("es_`suffix'") (`k') `row'
        }
    }
    postclose C

    use `covariance', clear
    gen str40 specification = "`spec'"
    gen str32 outcome = "`outcome'"
    order specification outcome term event_time
    export delimited using "$TAB/twfe_covariance_`spec'_`outcome'.csv", replace

    use `active_data', clear
end


capture program drop run_long_difference
program define run_long_difference
    syntax, SPEC(string) OUTCOME(name) UNITVAR(name) ///
        [DOSEVAR(name) FAMILYFE(varlist) CLUSTERVAR(name) SAMPLEVAR(name)]

    if "`dosevar'" == "" local dosevar exposure_10pp
    if "`clustervar'" == "" local clustervar cno4_id

    preserve
        keep if inlist(event_time, 0, 36)
        if "`samplevar'" != "" keep if `samplevar' == 1
        keep if !missing(`outcome', `dosevar', `clustervar')

        local reshapevars `outcome' `dosevar' `clustervar' `familyfe'
        local reshapevars : list uniq reshapevars
        keep `unitvar' event_time `reshapevars'
        isid `unitvar' event_time
        reshape wide `reshapevars', i(`unitvar') j(event_time)

        keep if !missing(`outcome'0, `outcome'36, `dosevar'0, `dosevar'36)
        gen double delta_y = `outcome'36 - `outcome'0
        * Exposure is occupation-specific and time-invariant; use its single
        * endpoint value directly rather than averaging duplicated values.
        gen double longdiff_dose = `dosevar'0

        local familywide
        foreach family of local familyfe {
            local familywide `familywide' `family'0
        }

        if "`familywide'" == "" {
            regress delta_y longdiff_dose, vce(cluster `clustervar'0)
        }
        else {
            reghdfe delta_y longdiff_dose, absorb(`familywide') ///
                vce(cluster `clustervar'0)
        }

        local observations = e(N)
        local clusters = e(N_clust)
        lincom longdiff_dose
        local estimate = r(estimate)
        local se = r(se)
        local ci_low = r(lb)
        local ci_high = r(ub)

        clear
        set obs 1
        gen str48 specification = "`spec'"
        gen str32 outcome = "`outcome'"
        gen str32 dosevar = "`dosevar'"
        gen double estimate = `estimate'
        gen double se = `se'
        gen double ci_low = `ci_low'
        gen double ci_high = `ci_high'
        gen double effect_percent = 100 * estimate
        gen int start_event = 0
        gen int end_event = 36
        gen long observations = `observations'
        gen long clusters = `clusters'
        export delimited using ///
            "$TAB/twfe_longdiff_`spec'_`outcome'.csv", replace
    restore
end


capture program drop post_pretrend_test
program define post_pretrend_test
    syntax, HANDLE(name) SPEC(string) OUTCOME(string) WINDOW(string) VARS(string)

    local variables `vars'
    local npre : word count `variables'
    if `npre' < 2 exit

    test `variables'
    post `handle' ("`spec'") ("`outcome'") ("`window'") ///
        ("joint_equal_zero") (r(F)) (r(df)) (r(df_r)) (r(p)) (e(N)) (e(N_clust))

    local first : word 1 of `variables'
    local restrictions
    forvalues j = 2/`npre' {
        local variable : word `j' of `variables'
        local restrictions `restrictions' (`variable' = `first')
    }
    test `restrictions'
    post `handle' ("`spec'") ("`outcome'") ("`window'") ///
        ("joint_equal_coefficients") (r(F)) (r(df)) (r(df_r)) (r(p)) (e(N)) (e(N_clust))
end


capture program drop run_twfe
program define run_twfe
    syntax, SPEC(string) OUTCOME(name) ABSORB(string) ///
        [DOSEVAR(name) CLUSTERVAR(name) EXPORTFIG]

    if "`dosevar'" == "" local dosevar exposure_10pp
    if "`clustervar'" == "" local clustervar cno4_id

    tempfile source_data event_results average_results longrun_results pretrend_results
    save `source_data', replace

    keep if inrange(event_time, $ES_MIN, $ES_MAX)
    keep if !missing(`outcome', `dosevar', `clustervar')
    quietly levelsof event_time, local(observed_event_values)
    make_continuous_event_terms, dosevar(`dosevar')
    event_varlists
    local all `r(all)'

    local postvars
    local prefull
    local preearly
    local prerecent
    local longrunvars
    foreach k of local observed_event_values {
        if `k' < 0 local suffix "m`=abs(`k')'"
        else local suffix "p`k'"
        if `k' != -1 {
            if inrange(`k', 1, $ES_MAX) local postvars `postvars' es_`suffix'
            if inrange(`k', $ES_MIN, -2) local prefull `prefull' es_`suffix'
            if inrange(`k', $ES_MIN, -10) local preearly `preearly' es_`suffix'
            if inrange(`k', -10, -2) local prerecent `prerecent' es_`suffix'
            if inrange(`k', 34, 38) local longrunvars `longrunvars' es_`suffix'
        }
    }

    reghdfe `outcome' `all', absorb(`absorb') vce(cluster `clustervar')

    local observations = e(N)
    local clusters = e(N_clust)

    postfile E str40 specification str32 outcome str32 dosevar ///
        int event_time double estimate se ci_low ci_high ///
        long observations clusters using `event_results', replace

    forvalues k = $ES_MIN/$ES_MAX {
        if `k' < 0 local suffix "m`=abs(`k')'"
        else local suffix "p`k'"
        local present : list posof "`k'" in observed_event_values

        if `present' == 0 {
            post E ("`spec'") ("`outcome'") ("`dosevar'") ///
                (`k') (.) (.) (.) (.) (`observations') (`clusters')
        }
        else if `k' == -1 {
            post E ("`spec'") ("`outcome'") ("`dosevar'") ///
                (`k') (0) (0) (0) (0) (`observations') (`clusters')
        }
        else {
            local b = _b[es_`suffix']
            local s = _se[es_`suffix']
            post E ("`spec'") ("`outcome'") ("`dosevar'") ///
                (`k') (`b') (`s') (`b' - 1.96*`s') (`b' + 1.96*`s') ///
                (`observations') (`clusters')
        }
    }
    postclose E

    * Average event-study coefficient over event times 1--40.
    local npost : word count `postvars'
    local expression
    forvalues j = 1/`npost' {
        local variable : word `j' of `postvars'
        if `j' == 1 local expression "(1/`npost')*`variable'"
        else local expression "`expression' + (1/`npost')*`variable'"
    }
    lincom `expression'
    local average = r(estimate)
    local average_se = r(se)

    postfile A str40 specification str32 outcome str32 dosevar ///
        double estimate se ci_low ci_high effect_percent ///
        int post_start post_end post_periods ///
        long observations clusters using `average_results', replace
    post A ("`spec'") ("`outcome'") ("`dosevar'") ///
        (`average') (`average_se') ///
        (`average' - 1.96*`average_se') (`average' + 1.96*`average_se') ///
        (100*`average') (1) ($ES_MAX) (`npost') ///
        (`observations') (`clusters')
    postclose A

    * Long-run marginal effect centered on November 2025 (event time 36).
    local nlong : word count `longrunvars'
    if `nlong' != 5 {
        display as error "Expected event times 34--38 for the long-run estimate."
        exit 459
    }
    local long_expression
    forvalues j = 1/`nlong' {
        local variable : word `j' of `longrunvars'
        if `j' == 1 local long_expression "(1/`nlong')*`variable'"
        else local long_expression "`long_expression' + (1/`nlong')*`variable'"
    }
    lincom `long_expression'
    local longrun = r(estimate)
    local longrun_se = r(se)

    postfile L str40 specification str32 outcome str32 dosevar ///
        double estimate se ci_low ci_high effect_percent ///
        int event_start event_end event_periods ///
        long observations clusters using `longrun_results', replace
    post L ("`spec'") ("`outcome'") ("`dosevar'") ///
        (`longrun') (`longrun_se') ///
        (`longrun' - 1.96*`longrun_se') (`longrun' + 1.96*`longrun_se') ///
        (100*`longrun') (34) (38) (`nlong') ///
        (`observations') (`clusters')
    postclose L

    * Pre-treatment diagnostics for the full and recent pre-period windows.
    postfile P str40 specification str32 outcome str16 window str32 test ///
        double F_stat df_num df_den p_value long observations clusters ///
        using `pretrend_results', replace
    post_pretrend_test, handle(P) spec("`spec'") outcome("`outcome'") ///
        window("full_-21_-2") vars("`prefull'")
    post_pretrend_test, handle(P) spec("`spec'") outcome("`outcome'") ///
        window("early_-21_-10") vars("`preearly'")
    post_pretrend_test, handle(P) spec("`spec'") outcome("`outcome'") ///
        window("recent_-10_-2") vars("`prerecent'")
    postclose P

    * Export the covariance last because the helper temporarily changes data.
    export_covariance, spec("`spec'") outcome("`outcome'")

    use `event_results', clear
    sort event_time
    export delimited using "$TAB/twfe_event_`spec'_`outcome'.csv", replace

    if "`exportfig'" != "" {
        local yrange
        if strpos("`outcome'", "parados") local yrange "yscale(range(-.05 .15)) ylabel(-.05(.05).15)"
        if strpos("`outcome'", "contratos") local yrange "yscale(range(-.20 .20)) ylabel(-.20(.10).20)"

        twoway ///
            (rarea ci_low ci_high event_time, color(eltblue%35) lcolor(none)) ///
            (connected estimate event_time, lcolor("8 81 156") mcolor("8 81 156") ///
                msymbol(O) msize(vsmall) lwidth(medthin)), ///
            xline(0, lpattern(dash) lcolor(gs8)) ///
            yline(0, lcolor(gs8)) ///
            xlabel(-20(10)40) ///
            xtitle("Months relative to November 2022") ///
            ytitle("Marginal effect") ///
            title("") subtitle("") note("") legend(off) ///
            `yrange' graphregion(color(white)) plotregion(color(white))
        graph export "$FIG/twfe_event_`spec'_`outcome'.png", replace width(2200)
    }

    use `average_results', clear
    export delimited using "$TAB/twfe_average_`spec'_`outcome'.csv", replace

    use `longrun_results', clear
    export delimited using "$TAB/twfe_longrun_`spec'_`outcome'.csv", replace

    use `pretrend_results', clear
    export delimited using "$TAB/twfe_pretrend_`spec'_`outcome'.csv", replace

    use `source_data', clear
end


capture program drop run_binary_average
program define run_binary_average
    syntax, SPEC(string) OUTCOME(name) TREATVAR(name) SAMPLEVAR(name) ///
        ABSORB(string) [CLUSTERVAR(name)]

    if "`clustervar'" == "" local clustervar cno4_id

    preserve
        tempfile event_results pretrend_results
        keep if `samplevar' == 1
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        keep if !missing(`outcome', `treatvar', `clustervar')

        capture drop bes_*
        local all
        local postvars
        local prefull
        local preearly
        local prerecent
        forvalues k = $ES_MIN/$ES_MAX {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            if `k' != -1 {
                gen double bes_`suffix' = `treatvar' * (event_time == `k')
                local all `all' bes_`suffix'
                if inrange(`k', 1, $ES_MAX) local postvars `postvars' bes_`suffix'
                if inrange(`k', $ES_MIN, -2) local prefull `prefull' bes_`suffix'
                if inrange(`k', $ES_MIN, -10) local preearly `preearly' bes_`suffix'
                if inrange(`k', -10, -2) local prerecent `prerecent' bes_`suffix'
            }
        }

        reghdfe `outcome' `all', absorb(`absorb') vce(cluster `clustervar')
        local observations = e(N)
        local clusters = e(N_clust)

        postfile E str40 specification str32 outcome int event_time ///
            double estimate se ci_low ci_high long observations clusters ///
            using `event_results', replace
        forvalues k = $ES_MIN/$ES_MAX {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            if `k' == -1 {
                post E ("`spec'") ("`outcome'") (`k') ///
                    (0) (0) (0) (0) (`observations') (`clusters')
            }
            else {
                local estimate = _b[bes_`suffix']
                local se = _se[bes_`suffix']
                post E ("`spec'") ("`outcome'") (`k') ///
                    (`estimate') (`se') ///
                    (`estimate' - 1.96*`se') (`estimate' + 1.96*`se') ///
                    (`observations') (`clusters')
            }
        }
        postclose E

        postfile P str40 specification str32 outcome str16 window str32 test ///
            double F_stat df_num df_den p_value long observations clusters ///
            using `pretrend_results', replace
        post_pretrend_test, handle(P) spec("`spec'") outcome("`outcome'") ///
            window("full_-21_-2") vars("`prefull'")
        post_pretrend_test, handle(P) spec("`spec'") outcome("`outcome'") ///
            window("early_-21_-10") vars("`preearly'")
        post_pretrend_test, handle(P) spec("`spec'") outcome("`outcome'") ///
            window("recent_-10_-2") vars("`prerecent'")
        postclose P

        local npost : word count `postvars'
        local expression
        forvalues j = 1/`npost' {
            local variable : word `j' of `postvars'
            if `j' == 1 local expression "(1/`npost')*`variable'"
            else local expression "`expression' + (1/`npost')*`variable'"
        }
        lincom `expression'

        clear
        set obs 1
        gen str40 specification = "`spec'"
        gen str32 outcome = "`outcome'"
        gen double estimate = r(estimate)
        gen double se = r(se)
        gen double ci_low = estimate - 1.96*se
        gen double ci_high = estimate + 1.96*se
        gen long observations = `observations'
        gen long clusters = `clusters'
        gen int post_start = 1
        gen int post_end = $ES_MAX
        export delimited using "$TAB/twfe_binary_average_`spec'_`outcome'.csv", replace

        use `event_results', clear
        sort event_time
        export delimited using "$TAB/twfe_binary_event_`spec'_`outcome'.csv", replace

        use `pretrend_results', clear
        export delimited using "$TAB/twfe_binary_pretrend_`spec'_`outcome'.csv", replace
    restore
end

********************************************************************************
* 2. Identifying-support diagnostics
********************************************************************************

capture program drop export_support
program define export_support
    syntax, LEVEL(name)

    preserve
        keep cno4 cno1d cno2 exposure_nearest
        duplicates drop cno4, force

        bysort `level': egen occupations = count(cno4)
        bysort `level': egen zero_exposure = total(exposure_nearest == 0)
        bysort `level': egen positive_exposure = total(exposure_nearest > 0)
        bysort `level': egen mean_exposure = mean(exposure_nearest)
        bysort `level': egen sd_exposure = sd(exposure_nearest)
        bysort `level': egen min_exposure = min(exposure_nearest)
        bysort `level': egen max_exposure = max(exposure_nearest)
        gen range_exposure = max_exposure - min_exposure
        bysort `level': keep if _n == 1
        keep `level' occupations zero_exposure positive_exposure ///
            mean_exposure sd_exposure min_exposure max_exposure range_exposure
        sort `level'
        export delimited using "$TAB/exposure_support_within_`level'.csv", replace
    restore
end

********************************************************************************
* 3. HonestDiD helper for the benchmark TWFE event study
********************************************************************************

capture program drop run_honestdid_twfe
program define run_honestdid_twfe
    syntax, OUTCOME(string)

    local coef_file "$TAB/twfe_event_benchmark_twfe_`outcome'.csv"
    local vcv_file "$TAB/twfe_covariance_benchmark_twfe_`outcome'.csv"

    preserve
        import delimited using "`coef_file'", clear varnames(1)
        keep if inrange(event_time, -10, -2) | inrange(event_time, 0, 36)
        sort event_time
        count
        assert r(N) == 46
        mkmat estimate, matrix(b_column)
        matrix b_honest = b_column'

        import delimited using "`vcv_file'", clear varnames(1)
        ds cov_*
        local covariance_variables `r(varlist)'
        sort event_time
        gen long source_row = _n
        keep if inrange(event_time, -10, -2) | inrange(event_time, 0, 36)
        sort event_time
        levelsof source_row, local(selected_rows) clean

        matrix V_honest = J(46, 46, .)
        local i = 0
        foreach row_i of local selected_rows {
            local ++i
            local j = 0
            foreach row_j of local selected_rows {
                local ++j
                quietly summarize cov_`row_j' if source_row == `row_i', meanonly
                matrix V_honest[`i', `j'] = r(mean)
            }
        }

        matrix l_vec = J(37, 1, 0)
        matrix l_vec[1, 1] = -1
        matrix l_vec[37, 1] = 1
        local m_grid 0 .0025 .005 .01 .02 .04

        capture noisily honestdid, b(b_honest) vcov(V_honest) l_vec(l_vec) ///
            pre(1/9) post(10/46) mvec(`m_grid') delta(sd)
        if _rc {
            display as error "HonestDiD failed for `outcome'."
            restore
            exit _rc
        }

        local honest_object `s(HonestEventStudy)'
        mata: st_matrix("HCI_v1", `honest_object'.CI)
        matrix colnames HCI_v1 = M ci_low ci_high
        clear
        svmat double HCI_v1, names(col)
        gen str20 estimator = "Benchmark TWFE"
        gen str32 outcome = "`outcome'"
        gen str32 estimand = "November 2022-November 2025"
        gen str24 pre_window = "-10 to -2; -1 omitted"
        gen str16 post_window = "0 to 36"
        order estimator outcome estimand pre_window post_window M ci_low ci_high
        export delimited using "$TAB/honestdid_twfe_benchmark_`outcome'.csv", replace
    restore
end

********************************************************************************
* 4. SDID helpers
********************************************************************************

capture program drop make_cno1_month_basis
program define make_cno1_month_basis, rclass
    capture drop c1m_*
    quietly summarize ym_id, meanonly
    local first_time = r(min)
    local last_time = r(max)
    quietly summarize cno1d, meanonly
    local first_group = r(min)
    local last_group = r(max)

    * The first observed CNO1 family is omitted in every month. Together with
    * the unit and time effects used by projected adjustment, this spans
    * CNO1 x month effects without supplying every mutually exhaustive family
    * dummy in each month.
    local covariates
    forvalues group = `=`first_group'+1'/`last_group' {
        forvalues time = `first_time'/`last_time' {
            gen byte c1m_`group'_`time' = cno1d == `group' & ym_id == `time'
            quietly summarize c1m_`group'_`time'
            if r(sd) > 0 local covariates `covariates' c1m_`group'_`time'
            else drop c1m_`group'_`time'
        }
    }
    return local covariates "`covariates'"
end


capture program drop balance_sdid_panel
program define balance_sdid_panel
    keep if !missing(unit_id, ym_stata, sdid_treatment)
    duplicates drop unit_id ym_stata, force
    quietly distinct ym_stata
    local periods = r(ndistinct)
    bysort unit_id: egen int observed_periods = count(ym_stata)
    keep if observed_periods == `periods'
    drop observed_periods
end


capture program drop run_sdid_event_v1
program define run_sdid_event_v1
    syntax, SPEC(string) OUTCOME(name) [COVARIATES(string)]

    preserve
        keep if !missing(`outcome', exposure_nearest)
        balance_sdid_panel

        * Match the paper's common event window exactly: November 2022 is
        * event 0, October 2022 is event -1, and the last month is event 40.
        quietly levelsof event_time if inrange(event_time, 0, $ES_MAX), ///
            local(post_event_values)
        local effects : word count `post_event_values'
        quietly levelsof event_time if inrange(event_time, $ES_MIN, -1), ///
            local(pre_event_values)
        local placebos : word count `pre_event_values'

        local covariate_option
        if "`covariates'" != "" local covariate_option "covariates(`covariates')"

        set seed $SEED
        capture noisily sdid_event `outcome' unit_id ym_stata sdid_treatment, ///
            effects(`effects') placebo(`placebos') vce(placebo) ///
            brep($SDID_REPS) method(sdid) `covariate_option'
        if _rc {
            display as error "sdid_event failed: `spec' / `outcome'"
            restore
            exit _rc
        }

        matrix H_event = e(H)
        clear
        svmat double H_event
        gen row = _n
        drop if row == 1
        gen int event_time = .

        * sdid_event orders post effects forward, then placebo effects backward.
        * Map rows to actual calendar-relative values rather than row numbers.
        * This matters for panels with an absent calendar month (the age panel
        * has no observations at event time 18).
        local output_row = 0
        foreach k of local post_event_values {
            local ++output_row
            replace event_time = `k' in `output_row'
        }
        forvalues j = `placebos'(-1)1 {
            local k : word `j' of `pre_event_values'
            local ++output_row
            replace event_time = `k' in `output_row'
        }

        capture rename H_event1 estimate
        capture rename H_event2 se
        capture rename H_event3 ci_low
        capture rename H_event4 ci_high
        capture rename H_event5 switchers
        capture confirm variable se
        if _rc gen double se = .
        capture confirm variable ci_low
        if _rc gen double ci_low = estimate - 1.96*se
        capture confirm variable ci_high
        if _rc gen double ci_high = estimate + 1.96*se
        capture confirm variable switchers
        if _rc gen double switchers = .
        gen str40 specification = "`spec'"
        gen str32 outcome = "`outcome'"
        gen int placebo_repetitions = $SDID_REPS
        order specification outcome event_time estimate se ci_low ci_high switchers
        sort event_time
        export delimited using "$TAB/sdid_event_`spec'_`outcome'.csv", replace

        local event_axis
        if "`spec'" == "expanded_donor_cno1_month" & "`outcome'" == "ln_parados" {
            local event_axis "yscale(range(-0.05 0.10) noextend) ylabel(-0.05(0.025)0.10)"
        }

        twoway ///
   (rarea ci_low ci_high event_time, color(eltblue) lcolor(none)) ///
            (connected estimate event_time, lcolor("8 81 156") mcolor("8 81 156") ///
                msymbol(O) msize(vsmall) lwidth(medthin)), ///
            xline(0, lpattern(dash) lcolor("127 140 141")) ///
            yline(0, lcolor("127 140 141")) ///
            xtitle("Months relative to November 2022") ytitle("Synthetic DID effect") ///
            `event_axis' ///
            title("") subtitle("") note("") legend(off) ///
            graphregion(color(white)) plotregion(color(white))
        graph export "$FIG/sdid_event_`spec'_`outcome'.png", replace width(2200)
    restore
end


capture program drop run_sdid_average_paths_v1
program define run_sdid_average_paths_v1
    syntax, SPEC(string) OUTCOME(name) [COVARIATES(string) PATHONLY]

    tempfile source balanced unit_metadata titles
    save `source', replace

    keep if !missing(`outcome', exposure_nearest)
    balance_sdid_panel
    save `balanced', replace
    quietly count
    local observations = r(N)
    quietly distinct unit_id
    local units = r(ndistinct)
    quietly distinct unit_id if sdid_high == 1
    local treated_units = r(ndistinct)
    quietly distinct unit_id if sdid_donor == 1
    local donor_units = r(ndistinct)
    quietly summarize exposure_nearest if sdid_high == 1, meanonly
    local treated_exposure = r(mean)

    keep unit_id unit cno4 cno1d exposure_nearest sdid_high sdid_donor
    bysort unit_id: keep if _n == 1
    save `unit_metadata', replace

    capture confirm file "`script_dir'/data/raw/cno4_english_titles.csv"
    if !_rc {
        import delimited using "`script_dir'/data/raw/cno4_english_titles.csv", ///
            clear varnames(1) stringcols(1) encoding("UTF-8")
        keep cno4 occupation_title_english
        rename occupation_title_english occupation_title
        capture confirm string variable cno4
        if _rc tostring cno4, replace format("%04.0f")
        replace cno4 = string(real(cno4), "%04.0f")
        duplicates drop cno4, force
        save `titles', replace

        use `unit_metadata', clear
        merge m:1 cno4 using `titles', nogen keep(1 3)
    }
    capture confirm variable occupation_title
    if _rc gen str120 occupation_title = ""
    save `unit_metadata', replace

    use `balanced', clear

    levelsof ym_stata, local(time_values)
    levelsof unit_id if sdid_donor == 1, local(donor_values)

    local covariate_option
    if "`covariates'" != "" local covariate_option "covariates(`covariates', projected)"

    if "`pathonly'" == "" {
        capture noisily sdid `outcome' unit_id ym_stata sdid_treatment, ///
            vce(placebo) reps($SDID_REPS) seed($SEED) method(sdid) ///
            `covariate_option' mattitles
        if _rc {
            display as error "sdid failed: `spec' / `outcome'"
            use `source', clear
            exit _rc
        }

        local estimate = e(ATT)
        local standard_error = e(se)
    }

    * Re-estimate without inference because weights and paths are returned only
    * by the no-inference pass. The point estimator and covariate specification
    * are unchanged.
    capture noisily sdid `outcome' unit_id ym_stata sdid_treatment, ///
        vce(noinference) seed($SEED) method(sdid) `covariate_option' mattitles
    if _rc {
        display as error "sdid weight/path pass failed: `spec' / `outcome'"
        use `source', clear
        exit _rc
    }

    matrix M_series = e(series)
    matrix M_lambda = e(lambda)
    matrix M_omega = e(omega)

    if "`pathonly'" == "" {
        preserve
            clear
            set obs 1
            gen str40 specification = "`spec'"
            gen str32 outcome = "`outcome'"
            gen double estimate = `estimate'
            gen double se = `standard_error'
            gen double ci_low = estimate - 1.96*se
            gen double ci_high = estimate + 1.96*se
            gen double p_value = 2*(1-normal(abs(estimate/se)))
            gen double effect_percent = 100*(exp(estimate)-1)
            gen long observations = `observations'
            gen int units = `units'
            gen int treated_units = `treated_units'
            gen int donor_units = `donor_units'
            gen double treated_mean_exposure = `treated_exposure'
            gen int placebo_repetitions = $SDID_REPS
            export delimited using ///
                "$TAB/sdid_average_`spec'_`outcome'.csv", replace
        restore
    }

    preserve
        clear
        svmat double M_series
        rename M_series1 ym_stata
        rename M_series2 counterfactual
        rename M_series3 treated
        gen int event_time = ym_stata - $EVENT_MONTH
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        gen str40 specification = "`spec'"
        gen str32 outcome = "`outcome'"
        order specification outcome ym_stata event_time treated counterfactual
        export delimited using "$TAB/sdid_paths_`spec'_`outcome'.csv", replace

        local path_axis
        if "`spec'" == "expanded_donor_cno1_month" & "`outcome'" == "ln_parados" {
            local path_axis "yscale(range(6 8.5) noextend) ylabel(6(0.5)8.5)"
        }
        if "`spec'" == "expanded_donor_cno1_month" & "`outcome'" == "ln_contratos" {
            local path_axis "yscale(range(3.5 7.5) noextend) ylabel(3.5(1)7.5)"
        }
        twoway ///
            (line treated event_time, lcolor("8 81 156") lwidth(medthick)) ///
            (line counterfactual event_time, lcolor("86 180 233") lwidth(medthick)), ///
            xline(0, lpattern(dash) lcolor("127 140 141")) ///
            xtitle("Months relative to November 2022") ytitle("Log outcome") ///
            title("") subtitle("") note("") ///
            legend(order(1 "High exposure" 2 "Synthetic lower-exposure counterfactual") ///
                cols(1) position(2) ring(0) region(fcolor(white%80) lcolor(white))) ///
            `path_axis' ///
            graphregion(color(white)) plotregion(color(white))
        graph export "$FIG/sdid_paths_`spec'_`outcome'.png", replace width(2200)
    restore

    preserve
        clear
        svmat double M_lambda
        gen row = _n
        local usable_rows = rowsof(M_lambda) - 1
        keep if row <= `usable_rows'
        gen ym_stata = .
        local j = 1
        foreach time of local time_values {
            replace ym_stata = `time' in `j'
            local ++j
        }
        rename M_lambda1 lambda
        gen int event_time = ym_stata - $EVENT_MONTH
        gen str40 specification = "`spec'"
        gen str32 outcome = "`outcome'"
        order specification outcome ym_stata event_time lambda
        export delimited using "$TAB/sdid_lambda_`spec'_`outcome'.csv", replace
    restore

    preserve
        clear
        svmat double M_omega
        gen row = _n
        local usable_rows = rowsof(M_omega) - 1
        keep if row <= `usable_rows'
        gen unit_id = .
        local j = 1
        foreach donor of local donor_values {
            replace unit_id = `donor' in `j'
            local ++j
        }
        rename M_omega1 omega
        merge 1:1 unit_id using `unit_metadata', nogen keep(1 3)
        gen double weighted_exposure = omega*exposure_nearest
        quietly summarize omega, meanonly
        local omega_sum = r(sum)
        quietly summarize weighted_exposure, meanonly
        local donor_exposure = r(sum)
        gen double omega_sum = `omega_sum'
        gen double donor_weighted_exposure = `donor_exposure'
        gen double treated_mean_exposure = `treated_exposure'
        gen double exposure_contrast = treated_mean_exposure - donor_weighted_exposure
        gen str40 specification = "`spec'"
        gen str32 outcome = "`outcome'"
        order specification outcome unit_id cno4 cno1d occupation_title ///
            exposure_nearest omega omega_sum donor_weighted_exposure ///
            treated_mean_exposure exposure_contrast
        gsort -omega
        export delimited using "$TAB/sdid_omega_`spec'_`outcome'.csv", replace
    restore

    use `source', clear
end


capture program drop run_sdid_phase_v1
program define run_sdid_phase_v1
    syntax, SPEC(string) OUTCOME(name) PHASE(string) [PROJECTCNO1]

    preserve
        keep if !missing(`outcome', exposure_nearest)
        if "`phase'" == "adjustment" {
            keep if event_time < 0 | inrange(event_time, 0, 24)
            local phase_start = 0
            local phase_end = 24
        }
        else if "`phase'" == "later" {
            keep if event_time < 0 | inrange(event_time, 25, 40)
            local phase_start = 25
            local phase_end = 40
        }
        else {
            display as error "Unknown synthetic-DID phase: `phase'"
            restore
            exit 198
        }

        balance_sdid_panel
        quietly count
        local observations = r(N)
        quietly distinct unit_id
        local units = r(ndistinct)
        quietly distinct unit_id if sdid_high == 1
        local treated_units = r(ndistinct)
        quietly distinct unit_id if sdid_donor == 1
        local donor_units = r(ndistinct)

        local estimation_outcome `outcome'
        local projected = 0
        local projection_method "none"
        if "`projectcno1'" != "" {
            tempvar cno1_month_residual
            quietly reghdfe `outcome', absorb(cno1_ym) ///
                residuals(`cno1_month_residual') keepsingletons
            local estimation_outcome `cno1_month_residual'
            local projected = 1
            local projection_method "CNO1-by-month residualization"
        }

        set seed $SEED
        capture noisily sdid `estimation_outcome' unit_id ym_stata ///
            sdid_treatment, vce(placebo) reps($SDID_REPS) ///
            seed($SEED) method(sdid)
        if _rc {
            display as error ///
                "Phase-specific sdid failed: `spec' / `outcome' / `phase'"
            restore
            exit _rc
        }

        local estimate = e(ATT)
        local standard_error = e(se)
        clear
        set obs 1
        gen str40 specification = "`spec'"
        gen str32 outcome = "`outcome'"
        gen str12 phase = "`phase'"
        gen int event_start = `phase_start'
        gen int event_end = `phase_end'
        gen double estimate = `estimate'
        gen double se = `standard_error'
        gen double ci_low = estimate - 1.96*se
        gen double ci_high = estimate + 1.96*se
        gen double p_value = 2*(1-normal(abs(estimate/se)))
        gen double effect_percent = 100*(exp(estimate)-1)
        gen long observations = `observations'
        gen int units = `units'
        gen int treated_units = `treated_units'
        gen int donor_units = `donor_units'
        gen byte projected_cno1_month = `projected'
        gen str40 projection_method = "`projection_method'"
        gen int placebo_repetitions = $SDID_REPS
        order specification outcome phase event_start event_end estimate se ///
            ci_low ci_high p_value effect_percent observations units ///
            treated_units donor_units projected_cno1_month projection_method ///
            placebo_repetitions
        export delimited using ///
            "$TAB/sdid_phase_`spec'_`outcome'_`phase'.csv", replace
    restore
end


capture program drop produce_phase_outputs
program define produce_phase_outputs
    display as result "Producing adjustment- and later-period TWFE estimates"

    load_v1_panel using "$IN/est_total_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        run_phase_effects, spec("benchmark_twfe") outcome(`outcome') ///
            absorb("cno4_id ym_id")
        run_phase_effects, spec("preferred_cno1_month") outcome(`outcome') ///
            absorb("cno4_id cno1_ym")
        run_phase_effects, spec("preferred_cno1_month_cluster_cno3") ///
            outcome(`outcome') absorb("cno4_id cno1_ym") clustervar(cno3_id)
    }

    foreach outcome in ln_parados_p1 ln_contratos_p1 {
        run_phase_effects, spec("benchmark_log_plus_one") ///
            outcome(`outcome') absorb("cno4_id ym_id")
        run_phase_effects, spec("log_plus_one_cno1_month") ///
            outcome(`outcome') absorb("cno4_id cno1_ym")
        run_phase_effects, spec("log_plus_one_cno1_month_cluster_cno3") ///
            outcome(`outcome') absorb("cno4_id cno1_ym") clustervar(cno3_id)
    }

    foreach outcome in ln_parados ln_contratos {
        run_phase_effects, spec("benchmark_cosine_weighted") outcome(`outcome') ///
            dosevar(exposure_weighted_10pp) absorb("cno4_id ym_id")
        run_phase_effects, spec("cosine_weighted_cno1_month") outcome(`outcome') ///
            dosevar(exposure_weighted_10pp) absorb("cno4_id cno1_ym")
        run_phase_effects, spec("cosine_weighted_cno1_month_cluster_cno3") ///
            outcome(`outcome') dosevar(exposure_weighted_10pp) ///
            absorb("cno4_id cno1_ym") clustervar(cno3_id)

        run_phase_effects, spec("benchmark_rf_relative") outcome(`outcome') ///
            dosevar(exposure_rf_relative_10pp) absorb("cno4_id ym_id")
        run_phase_effects, spec("rf_relative_cno1_month") outcome(`outcome') ///
            dosevar(exposure_rf_relative_10pp) absorb("cno4_id cno1_ym")
        run_phase_effects, spec("rf_relative_cno1_month_cluster_cno3") ///
            outcome(`outcome') dosevar(exposure_rf_relative_10pp) ///
            absorb("cno4_id cno1_ym") clustervar(cno3_id)
    }

    gen byte binary_high_all = exposure_nearest > $HIGH_CUTOFF ///
        if !missing(exposure_nearest)
    gen byte binary_high_all_sample = !missing(exposure_nearest)
    foreach outcome in ln_parados ln_contratos {
        run_phase_effects, spec("binary_high_all_benchmark") outcome(`outcome') ///
            dosevar(binary_high_all) samplevar(binary_high_all_sample) ///
            absorb("cno4_id ym_id")
        run_phase_effects, spec("binary_high_all_preferred") outcome(`outcome') ///
            dosevar(binary_high_all) samplevar(binary_high_all_sample) ///
            absorb("cno4_id cno1_ym")
        run_phase_effects, spec("binary_high_all_preferred_cluster_cno3") ///
            outcome(`outcome') dosevar(binary_high_all) ///
            samplevar(binary_high_all_sample) absorb("cno4_id cno1_ym") ///
            clustervar(cno3_id)
    }

    levelsof cno1d, local(cno1_groups)
    tempfile leaveout_source
    save `leaveout_source', replace
    foreach group of local cno1_groups {
        use `leaveout_source', clear
        keep if cno1d != `group'
        foreach outcome in ln_parados ln_contratos {
            run_phase_effects, spec("leaveout_cno1_`group'") outcome(`outcome') ///
                absorb("cno4_id cno1_ym")
        }
    }

    use `leaveout_source', clear
    run_twfe, spec("trailing12_cno1_month") outcome(ln_contratos_12m) ///
        absorb("cno4_id cno1_ym")
    run_phase_effects, spec("trailing12_benchmark") ///
        outcome(ln_contratos_12m) absorb("cno4_id ym_id")
    run_phase_effects, spec("trailing12_cno1_month") ///
        outcome(ln_contratos_12m) absorb("cno4_id cno1_ym")
    run_phase_effects, spec("trailing12_cno1_month_cluster_cno3") ///
        outcome(ln_contratos_12m) absorb("cno4_id cno1_ym") ///
        clustervar(cno3_id)

    load_v1_panel using "$IN/est_province_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("province_cno1_month") outcome(`outcome') ///
            absorb("unit_id province_ym cno1_ym")
        run_phase_effects, spec("province_benchmark") outcome(`outcome') ///
            absorb("unit_id province_ym")
        run_phase_effects, spec("province_cno1_month") outcome(`outcome') ///
            absorb("unit_id province_ym cno1_ym")
        run_phase_effects, spec("province_cno1_month_cluster_cno3") ///
            outcome(`outcome') absorb("unit_id province_ym cno1_ym") ///
            clustervar(cno3_id)
    }

    load_v1_panel using "$IN/est_age3_cno4.csv"
    levelsof age3, local(age_groups)
    tempfile age_phase_source
    save `age_phase_source', replace
    foreach age of local age_groups {
        use `age_phase_source', clear
        keep if age3 == "`age'"
        local tag = lower(subinstr(subinstr(subinstr("`age'", " ", "_", .), "<", "lt", .), ">", "gt", .))
        foreach outcome in ln_parados ln_contratos {
            run_phase_effects, spec("age_`tag'_benchmark") outcome(`outcome') ///
                absorb("unit_id ym_id")
            run_phase_effects, spec("age_`tag'_cno1_month") outcome(`outcome') ///
                absorb("unit_id cno1_ym")
            run_phase_effects, spec("age_`tag'_cno1_month_cluster_cno3") ///
                outcome(`outcome') absorb("unit_id cno1_ym") clustervar(cno3_id)
        }
    }

    load_v1_panel using "$IN/est_gender_cno4.csv"
    levelsof gender, local(gender_groups)
    tempfile gender_phase_source
    save `gender_phase_source', replace
    foreach gender of local gender_groups {
        use `gender_phase_source', clear
        keep if gender == "`gender'"
        local tag = lower(subinstr("`gender'", " ", "_", .))
        foreach outcome in ln_parados ln_contratos {
            run_phase_effects, spec("gender_`tag'_benchmark") outcome(`outcome') ///
                absorb("unit_id ym_id")
            run_phase_effects, spec("gender_`tag'_cno1_month") outcome(`outcome') ///
                absorb("unit_id cno1_ym")
            run_phase_effects, spec("gender_`tag'_cno1_month_cluster_cno3") ///
                outcome(`outcome') absorb("unit_id cno1_ym") clustervar(cno3_id)
        }
    }
end

********************************************************************************
* 3A. Pooled age-group equality tests
********************************************************************************

capture program drop run_pooled_age_phase
program define run_pooled_age_phase
    syntax, OUTCOME(name)

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        keep if !missing(`outcome', exposure_10pp, cno4_id)

        gen byte age_under30 = age3 == "<18 to 29"
        gen byte age_3039 = age3 == "30-39"
        gen byte age_40plus = age3 == "40 to >44"

        foreach phase in adjustment later {
            if "`phase'" == "adjustment" local phase_indicator "inrange(event_time, 0, 24)"
            else local phase_indicator "inrange(event_time, 25, 40)"

            gen double dose_`phase'_under30 = exposure_10pp * age_under30 * (`phase_indicator')
            gen double dose_`phase'_3039 = exposure_10pp * age_3039 * (`phase_indicator')
            gen double dose_`phase'_40plus = exposure_10pp * age_40plus * (`phase_indicator')
        }

        reghdfe `outcome' dose_adjustment_under30 dose_adjustment_3039 ///
            dose_adjustment_40plus dose_later_under30 dose_later_3039 ///
            dose_later_40plus, absorb(unit_id age_cno1_ym) ///
            vce(cluster cno4_id)

        local observations = e(N)
        local clusters = e(N_clust)

        foreach phase in adjustment later {
            test dose_`phase'_under30 = dose_`phase'_3039 = dose_`phase'_40plus
            local p_equal_all_`phase' = r(p)
            test dose_`phase'_3039 = dose_`phase'_under30
            local p_3039_under30_`phase' = r(p)
            test dose_`phase'_3039 = dose_`phase'_40plus
            local p_3039_40plus_`phase' = r(p)
            test dose_`phase'_under30 = dose_`phase'_40plus
            local p_under30_40plus_`phase' = r(p)
        }

        tempfile pooled_age_results
        postfile P str24 outcome str16 phase str20 age_group ///
            double estimate se ci_low ci_high effect_percent ///
            p_equal_all p_3039_vs_under30 p_3039_vs_40plus ///
            p_under30_vs_40plus long observations clusters ///
            using `pooled_age_results', replace

        foreach phase in adjustment later {
            foreach age in under30 3039 40plus {
                if "`age'" == "under30" local age_label "Under 30"
                else if "`age'" == "3039" local age_label "30--39"
                else local age_label "40 or older"

                lincom dose_`phase'_`age'
                post P ("`outcome'") ("`phase'") ("`age_label'") ///
                    (r(estimate)) (r(se)) (r(lb)) (r(ub)) ///
                    (100*r(estimate)) (`p_equal_all_`phase'') ///
                    (`p_3039_under30_`phase'') (`p_3039_40plus_`phase'') ///
                    (`p_under30_40plus_`phase'') (`observations') (`clusters')
            }
        }
        postclose P

        use `pooled_age_results', clear
        export delimited using "$TAB/age_pooled_phase_`outcome'.csv", replace
    restore
end

capture program drop produce_pooled_age_tests
program define produce_pooled_age_tests
    display as result "Running pooled age-group equality tests"
    load_v1_panel using "$IN/est_age3_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        run_pooled_age_phase, outcome(`outcome')
    }
end

if "$V1_JEV_OD_ONLY" == "1" {
    display as result "V1_JEV_OD_ONLY=1: producing Jev O.D. robustness outputs"
    load_v1_panel using "$IN/est_total_cno4_jev.csv"

    * Match the O.D. long-difference design: two outcomes, three columns,
    * and occupation exposure scaled to a ten percentage-point change.
    foreach outcome in ln_parados ln_contratos {
        run_long_difference, spec("benchmark_twfe") outcome(`outcome') ///
            unitvar(unit_id)
        run_long_difference, spec("preferred_cno1_month") outcome(`outcome') ///
            unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("preferred_cno1_month_cluster_cno3") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d) ///
            clustervar(cno3_id)
    }

    foreach measure in nearest weighted direct {
        foreach outcome in ln_parados ln_contratos {
            run_long_difference, spec("benchmark_jev_`measure'") ///
                outcome(`outcome') dosevar(exposure_jev_`measure'_10pp) ///
                unitvar(unit_id)
            run_long_difference, spec("jev_`measure'_cno1_month") ///
                outcome(`outcome') dosevar(exposure_jev_`measure'_10pp) ///
                unitvar(unit_id) familyfe(cno1d)
            run_long_difference, spec("jev_`measure'_cno1_month_cluster_cno3") ///
                outcome(`outcome') dosevar(exposure_jev_`measure'_10pp) ///
                unitvar(unit_id) familyfe(cno1d) clustervar(cno3_id)
        }
    }

    * Preferred CNO1-by-month event studies used for the O.D.2(c)/O.D.3(c)
    * figure counterparts.
    foreach measure in nearest weighted direct {
        foreach outcome in ln_parados ln_contratos {
            run_twfe, spec("jev_`measure'_cno1_month") outcome(`outcome') ///
                dosevar(exposure_jev_`measure'_10pp) ///
                absorb("cno4_id cno1_ym")
        }
    }

    display as result "Jev O.D. robustness outputs completed."
    log close
    exit
}

if "$V1_ROBUST_PRETREND_ONLY" == "1" {
    display as result "Regenerating Table B.1 pre-treatment diagnostics"
    load_v1_panel using "$IN/est_total_cno4.csv"

    foreach outcome in ln_parados_p1 ln_contratos_p1 {
        run_twfe, spec("benchmark_log_plus_one") outcome(`outcome') ///
            absorb("cno4_id ym_id")
        run_twfe, spec("log_plus_one_cno1_month_cluster_cno3") ///
            outcome(`outcome') absorb("cno4_id cno1_ym") ///
            clustervar(cno3_id)
    }

    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("benchmark_cosine_weighted") outcome(`outcome') ///
            dosevar(exposure_weighted_10pp) absorb("cno4_id ym_id")
        run_twfe, spec("cosine_weighted_cno1_month_cluster_cno3") ///
            outcome(`outcome') dosevar(exposure_weighted_10pp) ///
            absorb("cno4_id cno1_ym") clustervar(cno3_id)

        run_twfe, spec("benchmark_rf_relative") outcome(`outcome') ///
            dosevar(exposure_rf_relative_10pp) absorb("cno4_id ym_id")
        run_twfe, spec("rf_relative_cno1_month_cluster_cno3") ///
            outcome(`outcome') dosevar(exposure_rf_relative_10pp) ///
            absorb("cno4_id cno1_ym") clustervar(cno3_id)
    }

    display as result "Table B.1 pre-treatment diagnostics completed."
    log close
    exit
}

if "$V1_PROVINCE_ONLY" == "1" {
    display as result "Regenerating province-panel estimates only"
    load_v1_panel using "$IN/est_province_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("province_cno1_month") outcome(`outcome') ///
            absorb("unit_id province_ym cno1_ym")
        run_phase_effects, spec("province_benchmark") outcome(`outcome') ///
            absorb("unit_id province_ym")
        run_phase_effects, spec("province_cno1_month") outcome(`outcome') ///
            absorb("unit_id province_ym cno1_ym")
        run_phase_effects, spec("province_cno1_month_cluster_cno3") ///
            outcome(`outcome') absorb("unit_id province_ym cno1_ym") ///
            clustervar(cno3_id)
    }

    display as result "Province-panel outputs completed."
    log close
    exit
}

if "$V1_SDID_PATH_ONLY" == "1" {
    display as result ///
        "Regenerating CNO1-by-month-adjusted synthetic-DID paths only"
    foreach outcome in ln_parados ln_contratos {
        load_v1_panel using "$IN/est_total_cno4.csv"
        make_cno1_month_basis
        local cno1_month_covariates `r(covariates)'
        run_sdid_average_paths_v1, spec("expanded_donor_cno1_month") ///
            outcome(`outcome') covariates("`cno1_month_covariates'") pathonly
    }
    display as result "Adjusted synthetic-DID paths completed."
    log close
    exit
}

if "$V1_SDID_EVENT_GRAPH_ONLY" == "1" {
    display as result "Regenerating CNO1-by-month-adjusted synthetic-DID event graphs from saved estimates"
    foreach outcome in ln_parados ln_contratos {
        import delimited using "$TAB/sdid_event_expanded_donor_cno1_month_`outcome'.csv", clear
        sort event_time
        local event_axis
        if "`outcome'" == "ln_parados" {
            local event_axis "yscale(range(-0.05 0.10) noextend) ylabel(-0.05(0.025)0.10)"
        }
        twoway ///
             (rarea ci_low ci_high event_time, color(eltblue) lcolor(none)) ///
            (connected estimate event_time, lcolor("8 81 156") mcolor("8 81 156") ///
                msymbol(O) msize(vsmall) lwidth(medthin)), ///
            xline(0, lpattern(dash) lcolor("127 140 141")) ///
            yline(0, lcolor("127 140 141")) ///
            xtitle("Months relative to November 2022") ytitle("Synthetic DID effect") ///
            `event_axis' title("") subtitle("") note("") legend(off) ///
            graphregion(color(white)) plotregion(color(white))
        graph export "$FIG/sdid_event_expanded_donor_cno1_month_`outcome'.png", replace width(2200)
    }
    display as result "Adjusted synthetic-DID event graphs completed."
    log close
    exit
}

if "$V1_SDID_EVENT_JOB" == "1" {
    if "$V1_SDID_JOB_OUTCOME" == "" {
        display as error "Synthetic-DID event job outcome is missing."
        log close
        exit 198
    }
    load_v1_panel using "$IN/est_total_cno4.csv"
    make_cno1_month_basis
    local cno1_month_covariates `r(covariates)'
    run_sdid_event_v1, spec("expanded_donor_cno1_month") ///
        outcome($V1_SDID_JOB_OUTCOME) ///
        covariates("`cno1_month_covariates'")
    display as result "Adjusted synthetic-DID event job completed."
    log close
    exit
}

if "$V1_SDID_PHASE_JOB" == "1" {
    if "$V1_SDID_JOB_SPEC" == "" | "$V1_SDID_JOB_OUTCOME" == "" | ///
        "$V1_SDID_JOB_PHASE" == "" {
        display as error "Synthetic-DID job parameters are incomplete."
        log close
        exit 198
    }
    load_v1_panel using "$IN/est_total_cno4.csv"
    if "$V1_SDID_JOB_SPEC" == "expanded_donor_cno1_month" {
        run_sdid_phase_v1, spec("$V1_SDID_JOB_SPEC") ///
            outcome($V1_SDID_JOB_OUTCOME) phase("$V1_SDID_JOB_PHASE") ///
            projectcno1
    }
    else {
        run_sdid_phase_v1, spec("$V1_SDID_JOB_SPEC") ///
            outcome($V1_SDID_JOB_OUTCOME) phase("$V1_SDID_JOB_PHASE")
    }
    display as result "Synthetic-DID phase job completed."
    log close
    exit
}

********************************************************************************
* Occupational feminization heterogeneity
********************************************************************************

capture program drop run_feminization_phase
program define run_feminization_phase
    syntax, OUTCOME(name) P25(real) P50(real) P75(real)

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        keep if !missing(`outcome', exposure_10pp, ///
            feminization_10pp_centered, cno4_id)

        gen double dose_adjustment = exposure_10pp * inrange(event_time, 0, 24)
        gen double dose_later = exposure_10pp * inrange(event_time, 25, 40)
        gen double fem_adjustment = feminization_10pp_centered * ///
            inrange(event_time, 0, 24)
        gen double fem_later = feminization_10pp_centered * ///
            inrange(event_time, 25, 40)
        gen double dose_fem_adjustment = exposure_10pp * fem_adjustment
        gen double dose_fem_later = exposure_10pp * fem_later

        reghdfe `outcome' dose_adjustment dose_later fem_adjustment fem_later ///
            dose_fem_adjustment dose_fem_later, ///
            absorb(unit_id cno1_ym) vce(cluster cno4_id)

        local observations = e(N)
        local clusters = e(N_clust)
        lincom dose_fem_adjustment
        local moderation_adjustment = r(estimate)
        local moderation_adjustment_se = r(se)
        local moderation_adjustment_p = 2 * ttail(e(df_r), abs(r(estimate) / r(se)))
        lincom dose_fem_later
        local moderation_later = r(estimate)
        local moderation_later_se = r(se)
        local moderation_later_p = 2 * ttail(e(df_r), abs(r(estimate) / r(se)))
        tempfile results
        postfile P str32 outcome str12 phase int percentile ///
            double feminization_10pp_centered estimate se ci_low ci_high ///
            equality_p moderation_estimate moderation_se moderation_p ///
            long observations clusters using `results', replace

        foreach percentile in 25 50 75 {
            if `percentile' == 25 local value = `p25'
            if `percentile' == 50 local value = `p50'
            if `percentile' == 75 local value = `p75'
            test dose_adjustment + `value' * dose_fem_adjustment = ///
                dose_later + `value' * dose_fem_later
            local equality_p = r(p)

            foreach phase in adjustment later {
                if "`phase'" == "adjustment" {
                    local base dose_adjustment
                    local interaction dose_fem_adjustment
                    local moderation = `moderation_adjustment'
                    local moderation_se = `moderation_adjustment_se'
                    local moderation_p = `moderation_adjustment_p'
                }
                else {
                    local base dose_later
                    local interaction dose_fem_later
                    local moderation = `moderation_later'
                    local moderation_se = `moderation_later_se'
                    local moderation_p = `moderation_later_p'
                }
                lincom `base' + `value' * `interaction'
                post P ("`outcome'") ("`phase'") (`percentile') (`value') ///
                    (r(estimate)) (r(se)) (r(lb)) (r(ub)) (`equality_p') ///
                    (`moderation') (`moderation_se') (`moderation_p') ///
                    (`observations') (`clusters')
            }
        }
        postclose P

        use `results', clear
        sort phase percentile
        export delimited using "$TAB/feminization_phase_`outcome'.csv", replace
    restore
end


capture program drop run_feminization_event
program define run_feminization_event
    syntax, OUTCOME(name) P25(real) P50(real) P75(real)

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        keep if !missing(`outcome', exposure_10pp, ///
            feminization_10pp_centered, cno4_id)

        local dose_terms
        local fem_terms
        local interaction_terms
        forvalues k = $ES_MIN/$ES_MAX {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            if `k' != -1 {
                gen double fd_`suffix' = exposure_10pp * (event_time == `k')
                gen double ff_`suffix' = feminization_10pp_centered * ///
                    (event_time == `k')
                gen double fdi_`suffix' = exposure_10pp * ff_`suffix'
                local dose_terms `dose_terms' fd_`suffix'
                local fem_terms `fem_terms' ff_`suffix'
                local interaction_terms `interaction_terms' fdi_`suffix'
            }
        }

        reghdfe `outcome' `dose_terms' `fem_terms' `interaction_terms', ///
            absorb(unit_id cno1_ym) vce(cluster cno4_id)

        local observations = e(N)
        local clusters = e(N_clust)
        tempfile results pretrends
        postfile Q str32 outcome int percentile str28 test ///
            double F_stat df_num df_den p_value ///
            long observations clusters using `pretrends', replace

        foreach percentile in 25 50 75 {
            if `percentile' == 25 local value = `p25'
            if `percentile' == 50 local value = `p50'
            if `percentile' == 75 local value = `p75'
            local zero_restrictions
            local equal_restrictions
            forvalues k = $ES_MIN/-2 {
                if `k' < 0 local suffix "m`=abs(`k')'"
                else local suffix "p`k'"
                local zero_restrictions `zero_restrictions' ///
                    (fd_`suffix' + (`value') * fdi_`suffix' = 0)
                if `k' != $ES_MIN {
                    local equal_restrictions `equal_restrictions' ///
                        (fd_`suffix' + (`value') * fdi_`suffix' = ///
                        fd_m21 + (`value') * fdi_m21)
                }
            }
            test `zero_restrictions'
            post Q ("`outcome'") (`percentile') ("joint_equal_zero") ///
                (r(F)) (r(df)) (r(df_r)) (r(p)) ///
                (`observations') (`clusters')
            test `equal_restrictions'
            post Q ("`outcome'") (`percentile') ("joint_equal_coefficients") ///
                (r(F)) (r(df)) (r(df_r)) (r(p)) ///
                (`observations') (`clusters')
        }
        postclose Q

        postfile P str32 outcome int percentile event_time ///
            double feminization_10pp_centered estimate se ci_low ci_high ///
            long observations clusters using `results', replace

        foreach percentile in 25 50 75 {
            if `percentile' == 25 local value = `p25'
            if `percentile' == 50 local value = `p50'
            if `percentile' == 75 local value = `p75'
            forvalues k = $ES_MIN/$ES_MAX {
                if `k' == -1 {
                    post P ("`outcome'") (`percentile') (`k') (`value') ///
                        (0) (0) (0) (0) (`observations') (`clusters')
                }
                else {
                    if `k' < 0 local suffix "m`=abs(`k')'"
                    else local suffix "p`k'"
                    lincom fd_`suffix' + `value' * fdi_`suffix'
                    post P ("`outcome'") (`percentile') (`k') (`value') ///
                        (r(estimate)) (r(se)) (r(lb)) (r(ub)) ///
                        (`observations') (`clusters')
                }
            }
        }
        postclose P

        use `results', clear
        sort percentile event_time
        export delimited using "$TAB/feminization_event_`outcome'.csv", replace

        use `pretrends', clear
        export delimited using "$TAB/feminization_pretrend_`outcome'.csv", replace
    restore
end


capture program drop run_feminization_median_phase
program define run_feminization_median_phase
    syntax, OUTCOME(name)

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        keep if !missing(`outcome', exposure_10pp, ///
            feminization_10pp_centered, cno4_id)

        capture drop fem_above_median
        gen byte fem_above_median = feminization_10pp_centered >= 0
        gen double dose_adjustment = exposure_10pp * inrange(event_time, 0, 24)
        gen double dose_later = exposure_10pp * inrange(event_time, 25, 40)
        gen double dose_adjustment_above = dose_adjustment * fem_above_median
        gen double dose_later_above = dose_later * fem_above_median
        gen double group_adjustment = fem_above_median * inrange(event_time, 0, 24)
        gen double group_later = fem_above_median * inrange(event_time, 25, 40)

        reghdfe `outcome' dose_adjustment dose_later ///
            dose_adjustment_above dose_later_above ///
            group_adjustment group_later, ///
            absorb(unit_id cno1_ym) vce(cluster cno4_id)

        local observations = e(N)
        local clusters = e(N_clust)
        test dose_adjustment = dose_later
        local p_below = r(p)
        test dose_adjustment + dose_adjustment_above = ///
            dose_later + dose_later_above
        local p_above = r(p)

        tempfile results
        postfile P str32 outcome str12 phase str28 group ///
            double estimate se ci_low ci_high equality_p ///
            long observations clusters using `results', replace

        foreach phase in adjustment later {
            if "`phase'" == "adjustment" {
                local base dose_adjustment
                local above dose_adjustment_above
                local p_equal_below `p_below'
                local p_equal_above `p_above'
            }
            else {
                local base dose_later
                local above dose_later_above
                local p_equal_below `p_below'
                local p_equal_above `p_above'
            }
            lincom `base'
            post P ("`outcome'") ("`phase'") ("below_median") ///
                (r(estimate)) (r(se)) (r(lb)) (r(ub)) (`p_equal_below') ///
                (`observations') (`clusters')
            lincom `base' + `above'
            post P ("`outcome'") ("`phase'") ("above_or_equal_median") ///
                (r(estimate)) (r(se)) (r(lb)) (r(ub)) (`p_equal_above') ///
                (`observations') (`clusters')
        }
        postclose P

        use `results', clear
        sort phase group
        export delimited using "$TAB/feminization_median_phase_`outcome'.csv", replace
    restore
end


capture program drop run_feminization_median_event
program define run_feminization_median_event
    syntax, OUTCOME(name) [DETRENDed]

    local event_stub "feminization_median_event"
    local pretrend_stub "feminization_median_pretrend"
    local file_outcome "`outcome'"
    if "`detrended'" != "" {
        local event_stub "feminization_median_event_detrended"
        local pretrend_stub "feminization_median_pretrend_detrended"
        local file_outcome : subinstr local file_outcome "_detrended" "", all
    }

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        keep if !missing(`outcome', exposure_10pp, ///
            feminization_10pp_centered, cno4_id)

        capture drop fem_above_median
        gen byte fem_above_median = feminization_10pp_centered >= 0
        local base_terms
        local above_terms
        local group_terms
        forvalues k = $ES_MIN/$ES_MAX {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            if `k' != -1 {
                gen double med_d_`suffix' = exposure_10pp * (event_time == `k')
                gen double med_da_`suffix' = med_d_`suffix' * fem_above_median
                gen double med_g_`suffix' = fem_above_median * (event_time == `k')
                local base_terms `base_terms' med_d_`suffix'
                local above_terms `above_terms' med_da_`suffix'
                local group_terms `group_terms' med_g_`suffix'
            }
        }

        reghdfe `outcome' `base_terms' `above_terms' `group_terms', ///
            absorb(unit_id cno1_ym) vce(cluster cno4_id)

        local observations = e(N)
        local clusters = e(N_clust)
        tempfile results pretrends
        postfile Q str32 outcome str28 group str28 test ///
            double F_stat df_num df_den p_value ///
            long observations clusters using `pretrends', replace

        local below_zero
        local above_zero
        local below_equal
        local above_equal
        forvalues k = $ES_MIN/-2 {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            local below_zero `below_zero' (med_d_`suffix' = 0)
            local above_zero `above_zero' ///
                (med_d_`suffix' + med_da_`suffix' = 0)
            if `k' != $ES_MIN {
                local below_equal `below_equal' ///
                    (med_d_`suffix' = med_d_m21)
                local above_equal `above_equal' ///
                    (med_d_`suffix' + med_da_`suffix' = ///
                    med_d_m21 + med_da_m21)
            }
        }
        test `below_zero'
        post Q ("`outcome'") ("below_median") ("joint_equal_zero") ///
            (r(F)) (r(df)) (r(df_r)) (r(p)) ///
            (`observations') (`clusters')
        test `below_equal'
        post Q ("`outcome'") ("below_median") ("joint_equal_coefficients") ///
            (r(F)) (r(df)) (r(df_r)) (r(p)) ///
            (`observations') (`clusters')
        test `above_zero'
        post Q ("`outcome'") ("above_or_equal_median") ("joint_equal_zero") ///
            (r(F)) (r(df)) (r(df_r)) (r(p)) ///
            (`observations') (`clusters')
        test `above_equal'
        post Q ("`outcome'") ("above_or_equal_median") ("joint_equal_coefficients") ///
            (r(F)) (r(df)) (r(df_r)) (r(p)) ///
            (`observations') (`clusters')
        postclose Q

        postfile P str32 outcome str28 group int event_time ///
            double estimate se ci_low ci_high ///
            long observations clusters using `results', replace
        forvalues k = $ES_MIN/$ES_MAX {
            if `k' == -1 {
                foreach group in below_median above_or_equal_median {
                    post P ("`outcome'") ("`group'") (`k') ///
                        (0) (0) (0) (0) (`observations') (`clusters')
                }
            }
            else {
                if `k' < 0 local suffix "m`=abs(`k')'"
                else local suffix "p`k'"
                lincom med_d_`suffix'
                post P ("`outcome'") ("below_median") (`k') ///
                    (r(estimate)) (r(se)) (r(lb)) (r(ub)) ///
                    (`observations') (`clusters')
                lincom med_d_`suffix' + med_da_`suffix'
                post P ("`outcome'") ("above_or_equal_median") (`k') ///
                    (r(estimate)) (r(se)) (r(lb)) (r(ub)) ///
                    (`observations') (`clusters')
            }
        }
        postclose P

        use `results', clear
        sort group event_time
        export delimited using "$TAB/`event_stub'_`file_outcome'.csv", replace
        use `pretrends', clear
        export delimited using "$TAB/`pretrend_stub'_`file_outcome'.csv", replace
    restore
end


capture program drop prep_fem_detrended
program define prep_fem_detrended
    * Remove common month effects and CNO4-specific linear trends estimated only before the shock.
    foreach outcome in ln_parados ln_contratos {
        quietly regress `outcome' i.ym_stata i.cno4_id##c.ym_stata ///
            if event_time < 0 & !missing(`outcome', ym_stata, cno4_id)
        predict double fitted_detrended_`outcome', xb
        gen double `outcome'_detrended = `outcome' - fitted_detrended_`outcome'
        drop fitted_detrended_`outcome'
    }
end


capture program drop produce_feminization_analysis
program define produce_feminization_analysis
    import delimited using "$TAB/feminization_percentiles_v1.csv", ///
        clear varnames(1)
    quietly summarize female_share_10pp_centered if percentile == 25, meanonly
    local p25 = r(mean)
    quietly summarize female_share_10pp_centered if percentile == 50, meanonly
    local p50 = r(mean)
    quietly summarize female_share_10pp_centered if percentile == 75, meanonly
    local p75 = r(mean)

    load_v1_panel using "$IN/est_feminization_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        run_feminization_phase, outcome(`outcome') ///
            p25(`p25') p50(`p50') p75(`p75')
        run_feminization_event, outcome(`outcome') ///
            p25(`p25') p50(`p50') p75(`p75')
        run_feminization_median_phase, outcome(`outcome')
        run_feminization_median_event, outcome(`outcome')
    }

    prep_fem_detrended
    foreach outcome in ln_parados ln_contratos {
        run_feminization_median_event, outcome(`outcome'_detrended) detrended
    }
end


if "$V1_FEMINIZATION_ONLY" == "1" {
    display as result ///
        "V1_FEMINIZATION_ONLY=1: running feminization analysis"
    produce_feminization_analysis
    display as result "Feminization outputs completed."
    log close
    exit
}


if "$V1_SDID_PHASE_ONLY" == "1" {
    display as result ///
        "Estimating adjustment- and later-period synthetic DID effects"
    load_v1_panel using "$IN/est_total_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        foreach phase in adjustment later {
            run_sdid_phase_v1, spec("expanded_donor") ///
                outcome(`outcome') phase("`phase'")
            run_sdid_phase_v1, spec("expanded_donor_cno1_month") ///
                outcome(`outcome') phase("`phase'") projectcno1
        }
    }

    display as result "Phase-specific synthetic DID outputs completed."
    log close
    exit
}

if "$V1_PHASE_ONLY" == "1" {
    produce_phase_outputs
    display as result "Adjustment- and later-period outputs completed."
    log close
    exit
}

* Development/repair mode: regenerate only the aligned sdid_event outputs.
* Ordinary production runs leave V1_SDID_EVENT_ONLY unset and execute every
* section below.
if "$V1_SDID_EVENT_ONLY" == "1" {
    display as result "V1_SDID_EVENT_ONLY=1: regenerating aligned SDID events"

    if "$V1_SDID_EVENT_SKIP_TOTAL" != "1" {
        load_v1_panel using "$IN/est_total_cno4.csv"
        foreach outcome in ln_parados ln_contratos {
            run_sdid_event_v1, spec("expanded_donor") outcome(`outcome')
        }

        foreach outcome in ln_parados ln_contratos {
            load_v1_panel using "$IN/est_total_cno4.csv"
            make_cno1_month_basis
            local cno1_month_covariates `r(covariates)'
            run_sdid_event_v1, spec("expanded_donor_cno1_month") ///
                outcome(`outcome') covariates("`cno1_month_covariates'")
        }
    }

    load_v1_panel using "$IN/est_age3_cno4.csv"
    levelsof age3, local(age_groups)
    tempfile age_sdid_event_source
    save `age_sdid_event_source', replace
    foreach age of local age_groups {
        use `age_sdid_event_source', clear
        keep if age3 == "`age'"
        local tag = lower(subinstr(subinstr(subinstr("`age'", " ", "_", .), "<", "lt", .), ">", "gt", .))
        foreach outcome in ln_parados ln_contratos {
            run_sdid_event_v1, spec("age_`tag'_expanded_donor") outcome(`outcome')
        }
    }

    load_v1_panel using "$IN/est_gender_cno4.csv"
    levelsof gender, local(gender_groups)
    tempfile gender_sdid_event_source
    save `gender_sdid_event_source', replace
    foreach gender of local gender_groups {
        use `gender_sdid_event_source', clear
        keep if gender == "`gender'"
        local tag = lower(subinstr("`gender'", " ", "_", .))
        foreach outcome in ln_parados ln_contratos {
            run_sdid_event_v1, spec("gender_`tag'_expanded_donor") outcome(`outcome')
        }
    }

    display as result "Aligned SDID event outputs completed."
    log close
    exit
}

* Focused mode: regenerate all TWFE long-difference and robustness outputs
* without rerunning the synthetic-DiD or heterogeneity sections.
if "$V1_LONGDIFF_ONLY" == "1" {
    display as result "V1_LONGDIFF_ONLY=1: regenerating long-difference outputs"
    load_v1_panel using "$IN/est_total_cno4.csv"

    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("benchmark_twfe") outcome(`outcome') ///
            absorb("cno4_id ym_id")
        run_twfe, spec("preferred_cno1_month") outcome(`outcome') ///
            absorb("cno4_id cno1_ym")
        run_long_difference, spec("benchmark_twfe") outcome(`outcome') ///
            unitvar(unit_id)
        run_long_difference, spec("preferred_cno1_month") outcome(`outcome') ///
            unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("preferred_cno1_month_cluster_cno3") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d) ///
            clustervar(cno3_id)
    }

    foreach outcome in ln_parados_p1 ln_contratos_p1 {
        run_twfe, spec("log_plus_one_cno1_month") outcome(`outcome') ///
            absorb("cno4_id cno1_ym")
        run_long_difference, spec("benchmark_log_plus_one") ///
            outcome(`outcome') unitvar(unit_id)
        run_long_difference, spec("log_plus_one_cno1_month") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("log_plus_one_cno1_month_cluster_cno3") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d) ///
            clustervar(cno3_id)
    }

    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("cosine_weighted_cno1_month") outcome(`outcome') ///
            dosevar(exposure_weighted_10pp) absorb("cno4_id cno1_ym")
        run_long_difference, spec("benchmark_cosine_weighted") ///
            outcome(`outcome') dosevar(exposure_weighted_10pp) unitvar(unit_id)
        run_long_difference, spec("cosine_weighted_cno1_month") ///
            outcome(`outcome') dosevar(exposure_weighted_10pp) ///
            unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("cosine_weighted_cno1_month_cluster_cno3") ///
            outcome(`outcome') dosevar(exposure_weighted_10pp) ///
            unitvar(unit_id) familyfe(cno1d) clustervar(cno3_id)

        run_twfe, spec("rf_relative_cno1_month") outcome(`outcome') ///
            dosevar(exposure_rf_relative_10pp) absorb("cno4_id cno1_ym")
        run_long_difference, spec("benchmark_rf_relative") ///
            outcome(`outcome') dosevar(exposure_rf_relative_10pp) ///
            unitvar(unit_id)
        run_long_difference, spec("rf_relative_cno1_month") ///
            outcome(`outcome') dosevar(exposure_rf_relative_10pp) ///
            unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("rf_relative_cno1_month_cluster_cno3") ///
            outcome(`outcome') dosevar(exposure_rf_relative_10pp) ///
            unitvar(unit_id) familyfe(cno1d) clustervar(cno3_id)
    }

    levelsof cno1d, local(cno1_groups)
    tempfile total_longdiff_source
    save `total_longdiff_source', replace
    foreach group of local cno1_groups {
        use `total_longdiff_source', clear
        keep if cno1d != `group'
        run_long_difference, spec("leaveout_cno1_`group'") ///
            outcome(ln_parados) unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("leaveout_cno1_`group'") ///
            outcome(ln_contratos) unitvar(unit_id) familyfe(cno1d)
    }
    use `total_longdiff_source', clear

    * Binary treatment: high exposure versus all occupations at or below the
    * 75th-percentile cutoff. Middle-exposure occupations remain controls.
    gen byte binary_high_all = exposure_nearest > $HIGH_CUTOFF ///
        if !missing(exposure_nearest)
    gen byte binary_high_all_sample = !missing(exposure_nearest)
    foreach outcome in ln_parados ln_contratos {
        run_binary_average, spec("binary_high_all_preferred") outcome(`outcome') ///
            treatvar(binary_high_all) samplevar(binary_high_all_sample) ///
            absorb("cno4_id cno1_ym")
        run_binary_average, spec("binary_high_all_preferred_cluster_cno3") ///
            outcome(`outcome') treatvar(binary_high_all) ///
            samplevar(binary_high_all_sample) absorb("cno4_id cno1_ym") ///
            clustervar(cno3_id)
        run_long_difference, spec("binary_high_all_benchmark") ///
            outcome(`outcome') dosevar(binary_high_all) ///
            samplevar(binary_high_all_sample) unitvar(unit_id)
        run_long_difference, spec("binary_high_all_preferred") ///
            outcome(`outcome') dosevar(binary_high_all) ///
            samplevar(binary_high_all_sample) unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("binary_high_all_preferred_cluster_cno3") ///
            outcome(`outcome') dosevar(binary_high_all) ///
            samplevar(binary_high_all_sample) unitvar(unit_id) familyfe(cno1d) ///
            clustervar(cno3_id)
    }

    run_honestdid_twfe, outcome("ln_parados")
    run_honestdid_twfe, outcome("ln_contratos")

    load_v1_panel using "$IN/est_province_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("province_benchmark") outcome(`outcome') ///
            absorb("unit_id province_ym")
        run_twfe, spec("province_cno1_month") outcome(`outcome') ///
            absorb("unit_id province_ym cno1_ym")
        run_long_difference, spec("province_benchmark") outcome(`outcome') ///
            unitvar(unit_id) familyfe(province_id)
        run_long_difference, spec("province_cno1_month") outcome(`outcome') ///
            unitvar(unit_id) familyfe(province_id cno1d)
        run_long_difference, spec("province_cno1_month_cluster_cno3") ///
            outcome(`outcome') unitvar(unit_id) ///
            familyfe(province_id cno1d) clustervar(cno3_id)
    }

    display as result "Long-difference robustness outputs completed."
    log close
    exit
}

* Focused mode: regenerate the six-column TWFE heterogeneity table,
* subgroup pre-trend diagnostics, and preferred subgroup event studies.
if "$V1_HETERO_TWFE_ONLY" == "1" {
    display as result "V1_HETERO_TWFE_ONLY=1: regenerating TWFE heterogeneity"

    load_v1_panel using "$IN/est_age3_cno4.csv"
    levelsof age3, local(age_groups)
    tempfile age_heterogeneity_source
    save `age_heterogeneity_source', replace
    foreach age of local age_groups {
        use `age_heterogeneity_source', clear
        keep if age3 == "`age'"
        local tag = lower(subinstr(subinstr(subinstr("`age'", " ", "_", .), "<", "lt", .), ">", "gt", .))
        foreach outcome in ln_parados ln_contratos {
            run_twfe, spec("age_`tag'_benchmark") outcome(`outcome') ///
                absorb("unit_id ym_id")
            run_twfe, spec("age_`tag'_cno1_month") outcome(`outcome') ///
                absorb("unit_id cno1_ym")
            run_twfe, spec("age_`tag'_cno1_month_cluster_cno3") ///
                outcome(`outcome') absorb("unit_id cno1_ym") ///
                clustervar(cno3_id)
            run_long_difference, spec("age_`tag'_benchmark") ///
                outcome(`outcome') unitvar(unit_id)
            run_long_difference, spec("age_`tag'_cno1_month") ///
                outcome(`outcome') unitvar(unit_id) familyfe(cno1d)
            run_long_difference, spec("age_`tag'_cno1_month_cluster_cno3") ///
                outcome(`outcome') unitvar(unit_id) familyfe(cno1d) ///
                clustervar(cno3_id)
        }
    }

    load_v1_panel using "$IN/est_gender_cno4.csv"
    levelsof gender, local(gender_groups)
    tempfile gender_heterogeneity_source
    save `gender_heterogeneity_source', replace
    foreach gender of local gender_groups {
        use `gender_heterogeneity_source', clear
        keep if gender == "`gender'"
        local tag = lower(subinstr("`gender'", " ", "_", .))
        foreach outcome in ln_parados ln_contratos {
            run_twfe, spec("gender_`tag'_benchmark") outcome(`outcome') ///
                absorb("unit_id ym_id")
            run_twfe, spec("gender_`tag'_cno1_month") outcome(`outcome') ///
                absorb("unit_id cno1_ym")
            run_twfe, spec("gender_`tag'_cno1_month_cluster_cno3") ///
                outcome(`outcome') absorb("unit_id cno1_ym") ///
                clustervar(cno3_id)
            run_long_difference, spec("gender_`tag'_benchmark") ///
                outcome(`outcome') unitvar(unit_id)
            run_long_difference, spec("gender_`tag'_cno1_month") ///
                outcome(`outcome') unitvar(unit_id) familyfe(cno1d)
            run_long_difference, spec("gender_`tag'_cno1_month_cluster_cno3") ///
                outcome(`outcome') unitvar(unit_id) familyfe(cno1d) ///
                clustervar(cno3_id)
        }
    }

    display as result "TWFE heterogeneity outputs completed."
    log close
    exit
}

* Development/repair mode: regenerate age-group preferred-TWFE outputs after
* accounting explicitly for any unobserved calendar month.
if "$V1_AGE_TWFE_ONLY" == "1" {
    display as result "V1_AGE_TWFE_ONLY=1: regenerating age TWFE outputs"
    load_v1_panel using "$IN/est_age3_cno4.csv"
    levelsof age3, local(age_groups)
    tempfile age_twfe_repair_source
    save `age_twfe_repair_source', replace
    foreach age of local age_groups {
        use `age_twfe_repair_source', clear
        keep if age3 == "`age'"
        local tag = lower(subinstr(subinstr(subinstr("`age'", " ", "_", .), "<", "lt", .), ">", "gt", .))
        run_twfe, spec("age_`tag'_cno1_month") outcome(ln_parados) ///
            absorb("unit_id cno1_ym")
        run_twfe, spec("age_`tag'_cno1_month") outcome(ln_contratos) ///
            absorb("unit_id cno1_ym")
    }
    display as result "Age TWFE repair outputs completed."
    log close
    exit
}

* Focused mode for the six columns of the main long-run effects table.
if "$V1_MAIN_TABLE_ONLY" == "1" {
    display as result "V1_MAIN_TABLE_ONLY=1: regenerating main TWFE table inputs"
    load_v1_panel using "$IN/est_total_cno4.csv"

    run_twfe, spec("benchmark_twfe") outcome(ln_parados) ///
        absorb("cno4_id ym_id")
    run_twfe, spec("preferred_cno1_month") outcome(ln_parados) ///
        absorb("cno4_id cno1_ym")
    run_twfe, spec("preferred_cno1_month_cluster_cno3") ///
        outcome(ln_parados) absorb("cno4_id cno1_ym") ///
        clustervar(cno3_id)

    run_twfe, spec("benchmark_twfe") outcome(ln_contratos) ///
        absorb("cno4_id ym_id")
    run_twfe, spec("preferred_cno1_month") outcome(ln_contratos) ///
        absorb("cno4_id cno1_ym")
    run_twfe, spec("preferred_cno1_month_cluster_cno3") ///
        outcome(ln_contratos) absorb("cno4_id cno1_ym") ///
        clustervar(cno3_id)

    display as result "Main TWFE table inputs completed."
    log close
    exit
}

********************************************************************************
* 5. Preferred TWFE design and core benchmarks
********************************************************************************

display as result "Running preferred and benchmark TWFE specifications"
load_v1_panel using "$IN/est_total_cno4.csv"

export_support, level(cno1d)
export_support, level(cno2)

run_twfe, spec("preferred_cno1_month") outcome(ln_parados) ///
    absorb("cno4_id cno1_ym") exportfig
run_twfe, spec("preferred_cno1_month") outcome(ln_contratos) ///
    absorb("cno4_id cno1_ym") exportfig

run_twfe, spec("benchmark_twfe") outcome(ln_parados) ///
    absorb("cno4_id ym_id") exportfig
run_twfe, spec("benchmark_twfe") outcome(ln_contratos) ///
    absorb("cno4_id ym_id") exportfig

run_long_difference, spec("benchmark_twfe") outcome(ln_parados) ///
    unitvar(unit_id)
run_long_difference, spec("preferred_cno1_month") outcome(ln_parados) ///
    unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("preferred_cno1_month_cluster_cno3") ///
    outcome(ln_parados) unitvar(unit_id) familyfe(cno1d) ///
    clustervar(cno3_id)
run_long_difference, spec("benchmark_twfe") outcome(ln_contratos) ///
    unitvar(unit_id)
run_long_difference, spec("preferred_cno1_month") outcome(ln_contratos) ///
    unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("preferred_cno1_month_cluster_cno3") ///
    outcome(ln_contratos) unitvar(unit_id) familyfe(cno1d) ///
    clustervar(cno3_id)

if "$V1_SMOKE" == "1" {
    display as result "V1_SMOKE=1: core TWFE smoke test completed."
    log close
    exit
}

********************************************************************************
* 6. TWFE robustness checks
********************************************************************************

display as result "Running TWFE robustness checks"

* Outcome transformation.
run_twfe, spec("benchmark_log_plus_one") outcome(ln_parados_p1) ///
    absorb("cno4_id ym_id")
run_twfe, spec("benchmark_log_plus_one") outcome(ln_contratos_p1) ///
    absorb("cno4_id ym_id")
run_twfe, spec("log_plus_one_cno1_month") outcome(ln_parados_p1) ///
    absorb("cno4_id cno1_ym")
run_twfe, spec("log_plus_one_cno1_month") outcome(ln_contratos_p1) ///
    absorb("cno4_id cno1_ym")
run_twfe, spec("log_plus_one_cno1_month_cluster_cno3") ///
    outcome(ln_parados_p1) absorb("cno4_id cno1_ym") clustervar(cno3_id)
run_twfe, spec("log_plus_one_cno1_month_cluster_cno3") ///
    outcome(ln_contratos_p1) absorb("cno4_id cno1_ym") clustervar(cno3_id)
run_long_difference, spec("benchmark_log_plus_one") ///
    outcome(ln_parados_p1) unitvar(unit_id)
run_long_difference, spec("log_plus_one_cno1_month") ///
    outcome(ln_parados_p1) unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("log_plus_one_cno1_month_cluster_cno3") ///
    outcome(ln_parados_p1) unitvar(unit_id) familyfe(cno1d) ///
    clustervar(cno3_id)
run_long_difference, spec("benchmark_log_plus_one") ///
    outcome(ln_contratos_p1) unitvar(unit_id)
run_long_difference, spec("log_plus_one_cno1_month") ///
    outcome(ln_contratos_p1) unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("log_plus_one_cno1_month_cluster_cno3") ///
    outcome(ln_contratos_p1) unitvar(unit_id) familyfe(cno1d) ///
    clustervar(cno3_id)

* Alternative exposure measures.
run_twfe, spec("benchmark_cosine_weighted") outcome(ln_parados) ///
    dosevar(exposure_weighted_10pp) absorb("cno4_id ym_id")
run_twfe, spec("benchmark_cosine_weighted") outcome(ln_contratos) ///
    dosevar(exposure_weighted_10pp) absorb("cno4_id ym_id")
run_twfe, spec("cosine_weighted_cno1_month") outcome(ln_parados) ///
    dosevar(exposure_weighted_10pp) absorb("cno4_id cno1_ym")
run_twfe, spec("cosine_weighted_cno1_month") outcome(ln_contratos) ///
    dosevar(exposure_weighted_10pp) absorb("cno4_id cno1_ym")
run_twfe, spec("cosine_weighted_cno1_month_cluster_cno3") ///
    outcome(ln_parados) dosevar(exposure_weighted_10pp) ///
    absorb("cno4_id cno1_ym") clustervar(cno3_id)
run_twfe, spec("cosine_weighted_cno1_month_cluster_cno3") ///
    outcome(ln_contratos) dosevar(exposure_weighted_10pp) ///
    absorb("cno4_id cno1_ym") clustervar(cno3_id)
run_long_difference, spec("benchmark_cosine_weighted") outcome(ln_parados) ///
    dosevar(exposure_weighted_10pp) unitvar(unit_id)
run_long_difference, spec("cosine_weighted_cno1_month") outcome(ln_parados) ///
    dosevar(exposure_weighted_10pp) unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("cosine_weighted_cno1_month_cluster_cno3") ///
    outcome(ln_parados) dosevar(exposure_weighted_10pp) unitvar(unit_id) ///
    familyfe(cno1d) clustervar(cno3_id)
run_long_difference, spec("benchmark_cosine_weighted") outcome(ln_contratos) ///
    dosevar(exposure_weighted_10pp) unitvar(unit_id)
run_long_difference, spec("cosine_weighted_cno1_month") outcome(ln_contratos) ///
    dosevar(exposure_weighted_10pp) unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("cosine_weighted_cno1_month_cluster_cno3") ///
    outcome(ln_contratos) dosevar(exposure_weighted_10pp) unitvar(unit_id) ///
    familyfe(cno1d) clustervar(cno3_id)

run_twfe, spec("benchmark_rf_relative") outcome(ln_parados) ///
    dosevar(exposure_rf_relative_10pp) absorb("cno4_id ym_id")
run_twfe, spec("benchmark_rf_relative") outcome(ln_contratos) ///
    dosevar(exposure_rf_relative_10pp) absorb("cno4_id ym_id")
run_twfe, spec("rf_relative_cno1_month") outcome(ln_parados) ///
    dosevar(exposure_rf_relative_10pp) absorb("cno4_id cno1_ym")
run_twfe, spec("rf_relative_cno1_month") outcome(ln_contratos) ///
    dosevar(exposure_rf_relative_10pp) absorb("cno4_id cno1_ym")
run_twfe, spec("rf_relative_cno1_month_cluster_cno3") outcome(ln_parados) ///
    dosevar(exposure_rf_relative_10pp) absorb("cno4_id cno1_ym") ///
    clustervar(cno3_id)
run_twfe, spec("rf_relative_cno1_month_cluster_cno3") outcome(ln_contratos) ///
    dosevar(exposure_rf_relative_10pp) absorb("cno4_id cno1_ym") ///
    clustervar(cno3_id)
run_long_difference, spec("benchmark_rf_relative") outcome(ln_parados) ///
    dosevar(exposure_rf_relative_10pp) unitvar(unit_id)
run_long_difference, spec("rf_relative_cno1_month") outcome(ln_parados) ///
    dosevar(exposure_rf_relative_10pp) unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("rf_relative_cno1_month_cluster_cno3") ///
    outcome(ln_parados) dosevar(exposure_rf_relative_10pp) unitvar(unit_id) ///
    familyfe(cno1d) clustervar(cno3_id)
run_long_difference, spec("benchmark_rf_relative") outcome(ln_contratos) ///
    dosevar(exposure_rf_relative_10pp) unitvar(unit_id)
run_long_difference, spec("rf_relative_cno1_month") outcome(ln_contratos) ///
    dosevar(exposure_rf_relative_10pp) unitvar(unit_id) familyfe(cno1d)
run_long_difference, spec("rf_relative_cno1_month_cluster_cno3") ///
    outcome(ln_contratos) dosevar(exposure_rf_relative_10pp) unitvar(unit_id) ///
    familyfe(cno1d) clustervar(cno3_id)

run_twfe, spec("preferred_cno1_month_cluster_cno3") ///
    outcome(ln_parados) absorb("cno4_id cno1_ym") clustervar(cno3_id)
run_twfe, spec("preferred_cno1_month_cluster_cno3") ///
    outcome(ln_contratos) absorb("cno4_id cno1_ym") clustervar(cno3_id)
* Leave-one-CNO1-family-out sensitivity.
levelsof cno1d, local(cno1_groups)
tempfile total_for_leaveout
save `total_for_leaveout', replace
foreach group of local cno1_groups {
    use `total_for_leaveout', clear
    keep if cno1d != `group'
    run_twfe, spec("leaveout_cno1_`group'") outcome(ln_parados) ///
        absorb("cno4_id cno1_ym")
    run_twfe, spec("leaveout_cno1_`group'") outcome(ln_contratos) ///
        absorb("cno4_id cno1_ym")
    run_long_difference, spec("leaveout_cno1_`group'") ///
        outcome(ln_parados) unitvar(unit_id) familyfe(cno1d)
    run_long_difference, spec("leaveout_cno1_`group'") ///
        outcome(ln_contratos) unitvar(unit_id) familyfe(cno1d)
}
use `total_for_leaveout', clear

* Binary treatment: high exposure versus all occupations at or below the
* 75th-percentile cutoff. Middle-exposure occupations remain controls.
gen byte binary_high_all = exposure_nearest > $HIGH_CUTOFF ///
    if !missing(exposure_nearest)
gen byte binary_high_all_sample = !missing(exposure_nearest)
foreach outcome in ln_parados ln_contratos {
    run_binary_average, spec("binary_high_all_preferred") outcome(`outcome') ///
        treatvar(binary_high_all) samplevar(binary_high_all_sample) ///
        absorb("cno4_id cno1_ym")
    run_binary_average, spec("binary_high_all_preferred_cluster_cno3") ///
        outcome(`outcome') treatvar(binary_high_all) ///
        samplevar(binary_high_all_sample) absorb("cno4_id cno1_ym") ///
        clustervar(cno3_id)
    run_long_difference, spec("binary_high_all_benchmark") ///
        outcome(`outcome') dosevar(binary_high_all) ///
        samplevar(binary_high_all_sample) unitvar(unit_id)
    run_long_difference, spec("binary_high_all_preferred") ///
        outcome(`outcome') dosevar(binary_high_all) ///
        samplevar(binary_high_all_sample) unitvar(unit_id) familyfe(cno1d)
    run_long_difference, spec("binary_high_all_preferred_cluster_cno3") ///
        outcome(`outcome') dosevar(binary_high_all) ///
        samplevar(binary_high_all_sample) unitvar(unit_id) familyfe(cno1d) ///
        clustervar(cno3_id)
}

* HonestDiD sensitivity for the preferred TWFE event-study estimates.
run_honestdid_twfe, outcome("ln_parados")
run_honestdid_twfe, outcome("ln_contratos")

********************************************************************************
* 7. Province-disaggregated robustness
********************************************************************************

display as result "Running province x CNO4 robustness"
load_v1_panel using "$IN/est_province_cno4.csv"
run_twfe, spec("province_benchmark") outcome(ln_parados) ///
    absorb("unit_id province_ym")
run_twfe, spec("province_benchmark") outcome(ln_contratos) ///
    absorb("unit_id province_ym")
run_twfe, spec("province_cno1_month") outcome(ln_parados) ///
    absorb("unit_id province_ym cno1_ym")
run_twfe, spec("province_cno1_month") outcome(ln_contratos) ///
    absorb("unit_id province_ym cno1_ym")
run_twfe, spec("province_cno1_month_cluster_cno3") outcome(ln_parados) ///
    absorb("unit_id province_ym cno1_ym") clustervar(cno3_id)
run_twfe, spec("province_cno1_month_cluster_cno3") outcome(ln_contratos) ///
    absorb("unit_id province_ym cno1_ym") clustervar(cno3_id)

run_long_difference, spec("province_benchmark") outcome(ln_parados) ///
    unitvar(unit_id) familyfe(province_id)
run_long_difference, spec("province_cno1_month") outcome(ln_parados) ///
    unitvar(unit_id) familyfe(province_id cno1d)
run_long_difference, spec("province_cno1_month_cluster_cno3") ///
    outcome(ln_parados) unitvar(unit_id) familyfe(province_id cno1d) ///
    clustervar(cno3_id)
run_long_difference, spec("province_benchmark") outcome(ln_contratos) ///
    unitvar(unit_id) familyfe(province_id)
run_long_difference, spec("province_cno1_month") outcome(ln_contratos) ///
    unitvar(unit_id) familyfe(province_id cno1d)
run_long_difference, spec("province_cno1_month_cluster_cno3") ///
    outcome(ln_contratos) unitvar(unit_id) familyfe(province_id cno1d) ///
    clustervar(cno3_id)

********************************************************************************
* 8. Heterogeneity in the preferred TWFE design
********************************************************************************

display as result "Running age heterogeneity"
load_v1_panel using "$IN/est_age3_cno4.csv"
levelsof age3, local(age_groups)
tempfile age_twfe_source
save `age_twfe_source', replace
foreach age of local age_groups {
    use `age_twfe_source', clear
    keep if age3 == "`age'"
    local tag = lower(subinstr(subinstr(subinstr("`age'", " ", "_", .), "<", "lt", .), ">", "gt", .))
    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("age_`tag'_benchmark") outcome(`outcome') ///
            absorb("unit_id ym_id")
        run_twfe, spec("age_`tag'_cno1_month") outcome(`outcome') ///
            absorb("unit_id cno1_ym")
        run_twfe, spec("age_`tag'_cno1_month_cluster_cno3") ///
            outcome(`outcome') absorb("unit_id cno1_ym") ///
            clustervar(cno3_id)
        run_long_difference, spec("age_`tag'_benchmark") ///
            outcome(`outcome') unitvar(unit_id)
        run_long_difference, spec("age_`tag'_cno1_month") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("age_`tag'_cno1_month_cluster_cno3") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d) ///
            clustervar(cno3_id)
    }
}

* Formal pooled tests allow the age-specific exposure gradients to be compared
* within one covariance system.
produce_pooled_age_tests

display as result "Running gender heterogeneity"
load_v1_panel using "$IN/est_gender_cno4.csv"
levelsof gender, local(gender_groups)
tempfile gender_twfe_source
save `gender_twfe_source', replace
foreach gender of local gender_groups {
    use `gender_twfe_source', clear
    keep if gender == "`gender'"
    local tag = lower(subinstr("`gender'", " ", "_", .))
    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("gender_`tag'_benchmark") outcome(`outcome') ///
            absorb("unit_id ym_id")
        run_twfe, spec("gender_`tag'_cno1_month") outcome(`outcome') ///
            absorb("unit_id cno1_ym")
        run_twfe, spec("gender_`tag'_cno1_month_cluster_cno3") ///
            outcome(`outcome') absorb("unit_id cno1_ym") ///
            clustervar(cno3_id)
        run_long_difference, spec("gender_`tag'_benchmark") ///
            outcome(`outcome') unitvar(unit_id)
        run_long_difference, spec("gender_`tag'_cno1_month") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d)
        run_long_difference, spec("gender_`tag'_cno1_month_cluster_cno3") ///
            outcome(`outcome') unitvar(unit_id) familyfe(cno1d) ///
            clustervar(cno3_id)
    }
}

* Pooled post-treatment summaries used in the paper tables. The two bins
* distinguish the first 25 months after release from the later 16 months.
produce_phase_outputs

********************************************************************************
* 9. Occupational feminization
********************************************************************************

display as result "Running occupational-feminization analysis"
produce_feminization_analysis

********************************************************************************
* 10. Synthetic difference-in-differences
********************************************************************************

display as result "Running expanded-donor synthetic DID"
load_v1_panel using "$IN/est_total_cno4.csv"

* Preferred SDID: upper-tail exposure versus a synthetic combination of every
* occupation at or below the cutoff, with native CNO1-by-month adjustment.
foreach outcome in ln_parados ln_contratos {
    load_v1_panel using "$IN/est_total_cno4.csv"
    make_cno1_month_basis
    local cno1_month_covariates `r(covariates)'
    run_sdid_average_paths_v1, spec("expanded_donor_cno1_month") ///
        outcome(`outcome') covariates("`cno1_month_covariates'")
    run_sdid_event_v1, spec("expanded_donor_cno1_month") ///
        outcome(`outcome') covariates("`cno1_month_covariates'")
    foreach phase in adjustment later {
        run_sdid_phase_v1, spec("expanded_donor_cno1_month") ///
            outcome(`outcome') phase("`phase'") projectcno1
    }
}

display as result "Finished Estimates_TWFE_SDID_HonestDID_v1.do"
log close
