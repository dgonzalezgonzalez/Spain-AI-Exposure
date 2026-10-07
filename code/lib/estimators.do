capture program drop load_v1_panel
program define load_v1_panel
    syntax using/

    import delimited using "`using'", clear varnames(1) bindquote(strict) encoding("UTF-8")

    foreach v in ym_stata ym_index parados contratos contratos_12m ///
        ln_parados ln_contratos ln_contratos_12m ///
        ln_parados_p1 ln_contratos_p1 exposure_nearest exposure_10pp ///
        exposure_weighted exposure_weighted_10pp ///
        post_nov2022 ///
        may2024_age_backcast may2024_province_backcast female ///
        feminization_2017_2019 feminization_2021q1_2022q3 ///
        feminization_change feminization_10pp_centered ///
        feminization_three_group bls_ai_category_code ///
        frs_lm_aioe frs_lm_percentile frs_lm_percentile_10pp ///
        female_share_parados female_share_contratos ///
        log_gender_ratio_parados log_gender_ratio_contratos ///
        parados_female parados_male contratos_female contratos_male ///
        exposure_jev_nearest_10pp exposure_jev_weighted_10pp exposure_jev_direct_10pp jev_tier {
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
        [DOSEVAR(name) CLUSTERVAR(name) SAMPLEVAR(name)]

    if "`dosevar'" == "" local dosevar exposure_10pp
    if "`clustervar'" == "" local clustervar cno4_id

    tempfile source_data event_results average_results longrun_results pretrend_results
    save `source_data', replace

    keep if inrange(event_time, $ES_MIN, $ES_MAX)
    if "`samplevar'" != "" keep if `samplevar' == 1
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
            quietly count if event_time == `k'
            if `k' != -1 & r(N) > 0 {
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
            quietly count if event_time == `k'
            local event_observations = r(N)
            if `k' == -1 {
                post E ("`spec'") ("`outcome'") (`k') ///
                    (0) (0) (0) (0) (`observations') (`clusters')
            }
            else if `event_observations' == 0 {
                post E ("`spec'") ("`outcome'") (`k') ///
                    (.) (.) (.) (.) (`observations') (`clusters')
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
    quietly levelsof ym_stata, local(distinct_values)
    local periods : word count `distinct_values'
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
    quietly levelsof unit_id, local(distinct_values)
    local units : word count `distinct_values'
    quietly levelsof unit_id if sdid_high == 1, local(distinct_values)
    local treated_units : word count `distinct_values'
    quietly levelsof unit_id if sdid_donor == 1, local(distinct_values)
    local donor_units : word count `distinct_values'
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
    syntax, SPEC(string) OUTCOME(name) PHASE(string) [PROJECTCNO1 AUTOCOVARIATES]

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
        quietly levelsof unit_id, local(distinct_values)
    local units : word count `distinct_values'
        quietly levelsof unit_id if sdid_high == 1, local(distinct_values)
    local treated_units : word count `distinct_values'
        quietly levelsof unit_id if sdid_donor == 1, local(distinct_values)
    local donor_units : word count `distinct_values'

        local estimation_outcome `outcome'
        local projected = 0
        local projection_method "none"
        local covariate_option
        if "`projectcno1'" != "" {
            tempvar cno1_month_residual
            quietly reghdfe `outcome', absorb(cno1_ym) ///
                residuals(`cno1_month_residual') keepsingletons
            local estimation_outcome `cno1_month_residual'
            local projected = 1
            local projection_method "CNO1-by-month residualization"
        }
        else if "`autocovariates'" != "" {
            make_cno1_month_basis
            local covariates `r(covariates)'
            if "`covariates'" != "" {
                local covariate_option "covariates(`covariates', projected)"
                local projected = 1
                local projection_method "Projected CNO1-by-month covariates"
            }
        }

        set seed $SEED
        capture noisily sdid `estimation_outcome' unit_id ym_stata ///
            sdid_treatment, vce(placebo) reps($SDID_REPS) ///
            seed($SEED) method(sdid) `covariate_option'
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

    load_v1_panel using "$IN/est_age3_cno4.csv"
    gen byte sample_from_2022 = ym_stata >= tm(2022m1)
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
            run_phase_effects, spec("age_`tag'_cno1_month_no2021") ///
                outcome(`outcome') absorb("unit_id cno1_ym") ///
                samplevar(sample_from_2022)
            run_twfe, spec("age_`tag'_cno1_month_no2021") ///
                outcome(`outcome') absorb("unit_id cno1_ym") ///
                samplevar(sample_from_2022)
        }
    }

    load_v1_panel using "$IN/est_gender_cno4.csv"
    gen byte sample_from_2022 = ym_stata >= tm(2022m1)
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
            run_phase_effects, spec("gender_`tag'_cno1_month_no2021") ///
                outcome(`outcome') absorb("unit_id cno1_ym") ///
                samplevar(sample_from_2022)
            run_twfe, spec("gender_`tag'_cno1_month_no2021") ///
                outcome(`outcome') absorb("unit_id cno1_ym") ///
                samplevar(sample_from_2022)
        }
    }
end


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

        * Companion specification for the substantive younger-versus-older
        * hypothesis. It constrains the two younger groups to share a gradient
        * and tests that common under-40 gradient against the age-40-plus one.
        gen byte age_under40 = age_under30 | age_3039
        foreach phase in adjustment later {
            if "`phase'" == "adjustment" local phase_indicator "inrange(event_time, 0, 24)"
            else local phase_indicator "inrange(event_time, 25, 40)"

            gen double dose_`phase'_under40 = exposure_10pp * age_under40 * (`phase_indicator')
        }

        reghdfe `outcome' dose_adjustment_under40 dose_adjustment_40plus ///
            dose_later_under40 dose_later_40plus, absorb(unit_id age_cno1_ym) ///
            vce(cluster cno4_id)

        local pooled_observations = e(N)
        local pooled_clusters = e(N_clust)
        tempfile pooled_under40_results
        postfile Y str24 outcome str16 phase ///
            double under40_estimate under40_se older_estimate older_se ///
            difference difference_se p_under40_vs_40plus ///
            observations clusters using `pooled_under40_results', replace

        foreach phase in adjustment later {
            lincom dose_`phase'_under40
            local under40_estimate = r(estimate)
            local under40_se = r(se)

            lincom dose_`phase'_40plus
            local older_estimate = r(estimate)
            local older_se = r(se)

            lincom dose_`phase'_under40 - dose_`phase'_40plus
            local difference = r(estimate)
            local difference_se = r(se)

            test dose_`phase'_under40 = dose_`phase'_40plus
            local p_under40_40plus = r(p)

            post Y ("`outcome'") ("`phase'") ///
                (`under40_estimate') (`under40_se') ///
                (`older_estimate') (`older_se') ///
                (`difference') (`difference_se') (`p_under40_40plus') ///
                (`pooled_observations') (`pooled_clusters')
        }
        postclose Y

        use `pooled_age_results', clear
        export delimited using "$TAB/age_pooled_phase_`outcome'.csv", replace

        use `pooled_under40_results', clear
        export delimited using "$TAB/age_under40_pooled_phase_`outcome'.csv", replace
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


capture program drop run_feminization_median_phase
program define run_feminization_median_phase
    syntax, OUTCOME(name) [SAMPLEVAR(name) FILESUFFIX(string)]

    local output_stub "feminization_median_phase"
    if "`filesuffix'" != "" local output_stub "`output_stub'_`filesuffix'"

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
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
        export delimited using "$TAB/`output_stub'_`outcome'.csv", replace
    restore
end



capture program drop run_feminization_median_event
program define run_feminization_median_event
    syntax, OUTCOME(name) [DETRENDed SAMPLEVAR(name) FILESUFFIX(string)]

    local event_stub "feminization_median_event"
    local pretrend_stub "feminization_median_pretrend"
    local file_outcome "`outcome'"
    if "`detrended'" != "" {
        local event_stub "feminization_median_event_detrended"
        local pretrend_stub "feminization_median_pretrend_detrended"
        local file_outcome : subinstr local file_outcome "_detrended" "", all
    }
    if "`filesuffix'" != "" {
        local event_stub "`event_stub'_`filesuffix'"
        local pretrend_stub "`pretrend_stub'_`filesuffix'"
    }

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
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
        quietly summarize event_time if event_time <= -2, meanonly
        local test_min = r(min)
        local reference_suffix "m`=abs(`test_min')'"
        forvalues k = `test_min'/-2 {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            local below_zero `below_zero' (med_d_`suffix' = 0)
            local above_zero `above_zero' ///
                (med_d_`suffix' + med_da_`suffix' = 0)
            if `k' != `test_min' {
                local below_equal `below_equal' ///
                    (med_d_`suffix' = med_d_`reference_suffix')
                local above_equal `above_equal' ///
                    (med_d_`suffix' + med_da_`suffix' = ///
                    med_d_`reference_suffix' + med_da_`reference_suffix')
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



capture program drop run_fem3_phase
program define run_fem3_phase
    syntax, OUTCOME(name) [SPEC(string) SAMPLEVAR(name)]

    if "`spec'" == "" local spec "full"

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
        keep if !missing(`outcome', exposure_10pp, feminization_three_group, cno4_id)

        gen double tg_d_a = exposure_10pp * inrange(event_time, 0, 24)
        gen double tg_d_l = exposure_10pp * inrange(event_time, 25, 40)
        foreach group in 2 3 {
            gen double tg_d_a`group' = tg_d_a * (feminization_three_group == `group')
            gen double tg_d_l`group' = tg_d_l * (feminization_three_group == `group')
            gen double tg_g_a`group' = (feminization_three_group == `group') * ///
                inrange(event_time, 0, 24)
            gen double tg_g_l`group' = (feminization_three_group == `group') * ///
                inrange(event_time, 25, 40)
        }

        reghdfe `outcome' tg_d_a tg_d_l tg_d_a2 tg_d_l2 tg_d_a3 tg_d_l3 ///
            tg_g_a2 tg_g_l2 tg_g_a3 tg_g_l3, ///
            absorb(unit_id cno1_ym) vce(cluster cno4_id)

        local observations = e(N)
        local clusters = e(N_clust)
        tempfile results
        postfile P str32 outcome byte group str12 phase ///
            double estimate se ci_low ci_high equality_p ///
            long observations clusters using `results', replace

        foreach group in 1 2 3 {
            if `group' == 1 {
                local a_expr tg_d_a
                local l_expr tg_d_l
            }
            else {
                local a_expr tg_d_a + tg_d_a`group'
                local l_expr tg_d_l + tg_d_l`group'
            }
            test `a_expr' = `l_expr'
            local equality_p = r(p)
            lincom `a_expr'
            post P ("`outcome'") (`group') ("adjustment") ///
                (r(estimate)) (r(se)) (r(lb)) (r(ub)) (`equality_p') ///
                (`observations') (`clusters')
            lincom `l_expr'
            post P ("`outcome'") (`group') ("later") ///
                (r(estimate)) (r(se)) (r(lb)) (r(ub)) (`equality_p') ///
                (`observations') (`clusters')
        }
        postclose P
        use `results', clear
        sort group phase
        export delimited using ///
            "$TAB/feminization_three_group_phase_`spec'_`outcome'.csv", replace
    restore
end



capture program drop run_fem3_event
program define run_fem3_event
    syntax, OUTCOME(name)

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        keep if !missing(`outcome', exposure_10pp, feminization_three_group, cno4_id)

        local base_terms
        local middle_terms
        local high_terms
        local group_terms
        forvalues k = $ES_MIN/$ES_MAX {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            if `k' != -1 {
                gen double tg_e_`suffix' = exposure_10pp * (event_time == `k')
                gen double tg_e2_`suffix' = tg_e_`suffix' * ///
                    (feminization_three_group == 2)
                gen double tg_e3_`suffix' = tg_e_`suffix' * ///
                    (feminization_three_group == 3)
                gen double tg_g2_`suffix' = (feminization_three_group == 2) * ///
                    (event_time == `k')
                gen double tg_g3_`suffix' = (feminization_three_group == 3) * ///
                    (event_time == `k')
                local base_terms `base_terms' tg_e_`suffix'
                local middle_terms `middle_terms' tg_e2_`suffix'
                local high_terms `high_terms' tg_e3_`suffix'
                local group_terms `group_terms' tg_g2_`suffix' tg_g3_`suffix'
            }
        }

        reghdfe `outcome' `base_terms' `middle_terms' `high_terms' `group_terms', ///
            absorb(unit_id cno1_ym) vce(cluster cno4_id)
        local observations = e(N)
        local clusters = e(N_clust)

        tempfile results diagnostics
        postfile E str32 outcome byte group int event_time ///
            double estimate se ci_low ci_high long observations clusters ///
            using `results', replace
        postfile Q str32 outcome byte group str16 window str32 test ///
            double F_stat df_num df_den p_value long observations clusters ///
            using `diagnostics', replace

        foreach group in 1 2 3 {
            forvalues k = $ES_MIN/$ES_MAX {
                if `k' == -1 {
                    post E ("`outcome'") (`group') (`k') (0) (0) (0) (0) ///
                        (`observations') (`clusters')
                }
                else {
                    if `k' < 0 local suffix "m`=abs(`k')'"
                    else local suffix "p`k'"
                    if `group' == 1 local expression tg_e_`suffix'
                    if `group' == 2 local expression tg_e_`suffix' + tg_e2_`suffix'
                    if `group' == 3 local expression tg_e_`suffix' + tg_e3_`suffix'
                    lincom `expression'
                    post E ("`outcome'") (`group') (`k') ///
                        (r(estimate)) (r(se)) (r(lb)) (r(ub)) ///
                        (`observations') (`clusters')
                }
            }

            foreach window in full recent {
                if "`window'" == "full" {
                    local start $ES_MIN
                    local label "full_-21_-2"
                }
                else {
                    local start -10
                    local label "recent_-10_-2"
                }
                local zero
                local equal
                local first_expression
                forvalues k = `start'/-2 {
                    local suffix "m`=abs(`k')'"
                    if `group' == 1 local expression tg_e_`suffix'
                    if `group' == 2 local expression tg_e_`suffix' + tg_e2_`suffix'
                    if `group' == 3 local expression tg_e_`suffix' + tg_e3_`suffix'
                    local zero `zero' (`expression' = 0)
                    if `k' == `start' local first_expression `expression'
                    else local equal `equal' (`expression' = `first_expression')
                }
                test `zero'
                post Q ("`outcome'") (`group') ("`label'") ///
                    ("joint_equal_zero") (r(F)) (r(df)) (r(df_r)) (r(p)) ///
                    (`observations') (`clusters')
                test `equal'
                post Q ("`outcome'") (`group') ("`label'") ///
                    ("joint_equal_coefficients") (r(F)) (r(df)) (r(df_r)) (r(p)) ///
                    (`observations') (`clusters')
            }
        }
        postclose E
        postclose Q

        use `results', clear
        sort group event_time
        export delimited using ///
            "$TAB/feminization_three_group_event_`outcome'.csv", replace
        use `diagnostics', clear
        sort group window test
        export delimited using ///
            "$TAB/feminization_three_group_pretrend_`outcome'.csv", replace
    restore
end



capture program drop run_bls_categorical
program define run_bls_categorical
    syntax, OUTCOME(name) SPEC(string) ABSORB(string) [SAMPLEVAR(name)]

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
        keep if !missing(`outcome', bls_ai_category_code, cno4_id)

        foreach category in 2 3 4 {
            gen double bls_a`category' = (bls_ai_category_code == `category') * ///
                inrange(event_time, 0, 24)
            gen double bls_l`category' = (bls_ai_category_code == `category') * ///
                inrange(event_time, 25, 40)
        }
        reghdfe `outcome' bls_a2 bls_l2 bls_a3 bls_l3 bls_a4 bls_l4, ///
            absorb(`absorb') vce(cluster cno4_id)
        local observations = e(N)
        local clusters = e(N_clust)

        tempfile phase_results
        postfile P str40 specification str32 outcome byte category str12 phase ///
            double estimate se ci_low ci_high equality_p ///
            long observations clusters using `phase_results', replace
        foreach category in 2 3 4 {
            test bls_a`category' = bls_l`category'
            local equality_p = r(p)
            foreach phase in adjustment later {
                if "`phase'" == "adjustment" local variable bls_a`category'
                else local variable bls_l`category'
                lincom `variable'
                post P ("`spec'") ("`outcome'") (`category') ("`phase'") ///
                    (r(estimate)) (r(se)) (r(lb)) (r(ub)) (`equality_p') ///
                    (`observations') (`clusters')
            }
        }
        postclose P
        use `phase_results', clear
        sort category phase
        export delimited using ///
            "$TAB/bls_categorical_phase_`spec'_`outcome'.csv", replace
    restore

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
        keep if !missing(`outcome', bls_ai_category_code, cno4_id)
        quietly levelsof event_time, local(observed_event_values)
        local all_terms
        foreach k of local observed_event_values {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            if `k' != -1 {
                foreach category in 2 3 4 {
                    gen double bls`category'_`suffix' = ///
                        (bls_ai_category_code == `category') * (event_time == `k')
                    local all_terms `all_terms' bls`category'_`suffix'
                }
            }
        }
        reghdfe `outcome' `all_terms', absorb(`absorb') ///
            vce(cluster cno4_id)
        local observations = e(N)
        local clusters = e(N_clust)

        tempfile event_results diagnostics
        postfile E str40 specification str32 outcome byte category int event_time ///
            double estimate se ci_low ci_high long observations clusters ///
            using `event_results', replace
        postfile Q str40 specification str32 outcome byte category ///
            str16 window str32 test ///
            double F_stat df_num df_den p_value long observations clusters ///
            using `diagnostics', replace
        foreach category in 2 3 4 {
            forvalues k = $ES_MIN/$ES_MAX {
                local present : list posof "`k'" in observed_event_values
                if `present' == 0 {
                    post E ("`spec'") ("`outcome'") (`category') (`k') ///
                        (.) (.) (.) (.) (`observations') (`clusters')
                }
                else if `k' == -1 {
                    post E ("`spec'") ("`outcome'") (`category') (`k') ///
                        (0) (0) (0) (0) ///
                        (`observations') (`clusters')
                }
                else {
                    if `k' < 0 local suffix "m`=abs(`k')'"
                    else local suffix "p`k'"
                    local b = _b[bls`category'_`suffix']
                    local s = _se[bls`category'_`suffix']
                    post E ("`spec'") ("`outcome'") (`category') (`k') (`b') (`s') ///
                        (`b' - 1.96*`s') (`b' + 1.96*`s') ///
                        (`observations') (`clusters')
                }
            }
            foreach window in full early recent {
                if "`window'" == "full" {
                    local start $ES_MIN
                    local label "full_-21_-2"
                }
                else if "`window'" == "early" {
                    local start $ES_MIN
                    local end -10
                    local label "early_-21_-10"
                }
                else {
                    local start -10
                    local label "recent_-10_-2"
                }
                local variables
                foreach k of local observed_event_values {
                    local include = inrange(`k', `start', -2)
                    if "`window'" == "early" local include = inrange(`k', `start', `end')
                    if `include' {
                        local suffix "m`=abs(`k')'"
                        local variables `variables' bls`category'_`suffix'
                    }
                }
                local nvars : word count `variables'
                if `nvars' >= 2 {
                    test `variables'
                    post Q ("`spec'") ("`outcome'") (`category') ("`label'") ///
                        ("joint_equal_zero") (r(F)) (r(df)) (r(df_r)) (r(p)) ///
                        (`observations') (`clusters')
                    local first : word 1 of `variables'
                    local restrictions
                    forvalues j = 2/`nvars' {
                        local variable : word `j' of `variables'
                        local restrictions `restrictions' (`variable' = `first')
                    }
                    test `restrictions'
                    post Q ("`spec'") ("`outcome'") (`category') ("`label'") ///
                        ("joint_equal_coefficients") ///
                        (r(F)) (r(df)) (r(df_r)) (r(p)) ///
                        (`observations') (`clusters')
                }
            }
        }
        postclose E
        postclose Q
        use `event_results', clear
        sort category event_time
        export delimited using ///
            "$TAB/bls_categorical_event_`spec'_`outcome'.csv", replace
        use `diagnostics', clear
        sort category window test
        export delimited using ///
            "$TAB/bls_categorical_pretrend_`spec'_`outcome'.csv", replace
    restore
end



capture program drop produce_refinement_outputs
program define produce_refinement_outputs
    display as result "Running requested sample and exposure refinements"

    load_v1_panel using "$IN/est_total_cno4.csv"
    gen byte sample_from_2022 = ym_stata >= tm(2022m1)
    gen byte sample_frs_lm = !missing(frs_lm_percentile_10pp)
    gen byte sample_frs_lm_no2021 = sample_frs_lm & sample_from_2022
    gen byte binary_high_all = exposure_nearest > $HIGH_CUTOFF ///
        if !missing(exposure_nearest)
    gen byte binary_high_all_sample = !missing(exposure_nearest)
    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("preferred_cno1_month_no2021") outcome(`outcome') ///
            absorb("cno4_id cno1_ym") samplevar(sample_from_2022)
        run_phase_effects, spec("preferred_cno1_month_no2021") ///
            outcome(`outcome') absorb("cno4_id cno1_ym") ///
            samplevar(sample_from_2022)

        run_phase_effects, spec("binary_high_all_preferred_no2021") ///
            outcome(`outcome') dosevar(binary_high_all) ///
            samplevar(sample_from_2022) absorb("cno4_id cno1_ym")
        run_binary_average, spec("binary_high_all_benchmark") ///
            outcome(`outcome') treatvar(binary_high_all) ///
            samplevar(binary_high_all_sample) absorb("cno4_id ym_id")
        run_binary_average, spec("binary_high_all_preferred") ///
            outcome(`outcome') treatvar(binary_high_all) ///
            samplevar(binary_high_all_sample) absorb("cno4_id cno1_ym")
        run_binary_average, spec("binary_high_all_preferred_cluster_cno3") ///
            outcome(`outcome') treatvar(binary_high_all) ///
            samplevar(binary_high_all_sample) absorb("cno4_id cno1_ym") ///
            clustervar(cno3_id)
        run_binary_average, spec("binary_high_all_preferred_no2021") ///
            outcome(`outcome') treatvar(binary_high_all) ///
            samplevar(sample_from_2022) absorb("cno4_id cno1_ym")

        run_twfe, spec("frs_lm_benchmark") outcome(`outcome') ///
            dosevar(frs_lm_percentile_10pp) absorb("cno4_id ym_id")
        run_phase_effects, spec("frs_lm_benchmark") outcome(`outcome') ///
            dosevar(frs_lm_percentile_10pp) absorb("cno4_id ym_id")
        run_twfe, spec("frs_lm_cno1_month") outcome(`outcome') ///
            dosevar(frs_lm_percentile_10pp) absorb("cno4_id cno1_ym")
        run_phase_effects, spec("frs_lm_cno1_month") outcome(`outcome') ///
            dosevar(frs_lm_percentile_10pp) absorb("cno4_id cno1_ym")
        run_twfe, spec("frs_lm_cno1_month_no2021") outcome(`outcome') ///
            dosevar(frs_lm_percentile_10pp) absorb("cno4_id cno1_ym") ///
            samplevar(sample_frs_lm_no2021)
        run_phase_effects, spec("frs_lm_cno1_month_no2021") ///
            outcome(`outcome') dosevar(frs_lm_percentile_10pp) ///
            absorb("cno4_id cno1_ym") samplevar(sample_frs_lm_no2021)

        run_twfe, spec("nearest_common_frs_benchmark") outcome(`outcome') ///
            dosevar(exposure_10pp) absorb("cno4_id ym_id") ///
            samplevar(sample_frs_lm)
        run_phase_effects, spec("nearest_common_frs_benchmark") ///
            outcome(`outcome') dosevar(exposure_10pp) ///
            absorb("cno4_id ym_id") samplevar(sample_frs_lm)
        run_twfe, spec("nearest_common_frs_cno1_month") outcome(`outcome') ///
            dosevar(exposure_10pp) absorb("cno4_id cno1_ym") ///
            samplevar(sample_frs_lm)
        run_phase_effects, spec("nearest_common_frs_cno1_month") ///
            outcome(`outcome') dosevar(exposure_10pp) ///
            absorb("cno4_id cno1_ym") samplevar(sample_frs_lm)
        run_twfe, spec("nearest_common_frs_cno1_month_no2021") ///
            outcome(`outcome') dosevar(exposure_10pp) ///
            absorb("cno4_id cno1_ym") samplevar(sample_frs_lm_no2021)
        run_phase_effects, spec("nearest_common_frs_cno1_month_no2021") ///
            outcome(`outcome') dosevar(exposure_10pp) ///
            absorb("cno4_id cno1_ym") samplevar(sample_frs_lm_no2021)

        run_bls_categorical, outcome(`outcome') spec("benchmark") ///
            absorb("cno4_id ym_id")
        run_bls_categorical, outcome(`outcome') spec("preferred") ///
            absorb("cno4_id cno1_ym")
        run_bls_categorical, outcome(`outcome') spec("preferred_no2021") ///
            absorb("cno4_id cno1_ym") samplevar(sample_from_2022)
    }

    foreach outcome in ln_parados_p1 ln_contratos_p1 {
        run_twfe, spec("log_plus_one_cno1_month_no2021") ///
            outcome(`outcome') absorb("cno4_id cno1_ym") ///
            samplevar(sample_from_2022)
        run_phase_effects, spec("log_plus_one_cno1_month_no2021") ///
            outcome(`outcome') absorb("cno4_id cno1_ym") ///
            samplevar(sample_from_2022)
    }

    foreach outcome in ln_parados ln_contratos {
        run_twfe, spec("cosine_weighted_cno1_month_no2021") ///
            outcome(`outcome') dosevar(exposure_weighted_10pp) ///
            absorb("cno4_id cno1_ym") samplevar(sample_from_2022)
        run_phase_effects, spec("cosine_weighted_cno1_month_no2021") ///
            outcome(`outcome') dosevar(exposure_weighted_10pp) ///
            absorb("cno4_id cno1_ym") samplevar(sample_from_2022)

    }

    produce_main_province_outputs

    load_v1_panel using "$IN/est_feminization_cno4.csv"
    gen byte sample_from_2022 = ym_stata >= tm(2022m1)
    foreach outcome in ln_parados ln_contratos {
        run_fem3_phase, outcome(`outcome') spec("full")
        run_fem3_phase, outcome(`outcome') spec("no2021") ///
            samplevar(sample_from_2022)
        run_fem3_event, outcome(`outcome')
    }
end



capture program drop run_main_province_comparison
program define run_main_province_comparison
    syntax, OUTCOME(name) [NO2021]

    local specification "mainprovince_comparison"
    local file_suffix ""
    if "`no2021'" != "" {
        local specification "mainprovince_comparison_no2021"
        local file_suffix "_no2021"
    }

    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`no2021'" != "" keep if ym_stata >= tm(2022m1)
        keep if !missing(`outcome', exposure_10pp, cno4_id)
        gen byte main_province = inlist(province, "Madrid", "Barcelona")
        quietly levelsof event_time, local(observed_event_values)

        tempfile event_results pretrend_results phase_results
        local all
        local prefull_main
        local prefull_rest
        local preearly_main
        local preearly_rest
        local prerecent_main
        local prerecent_rest

        foreach k of local observed_event_values {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            if `k' != -1 {
                gen double geo_main_`suffix' = exposure_10pp * ///
                    (event_time == `k') * main_province
                gen double geo_rest_`suffix' = exposure_10pp * ///
                    (event_time == `k') * (1 - main_province)
                local all `all' geo_main_`suffix' geo_rest_`suffix'
                if inrange(`k', $ES_MIN, -2) {
                    local prefull_main `prefull_main' geo_main_`suffix'
                    local prefull_rest `prefull_rest' geo_rest_`suffix'
                }
                if inrange(`k', $ES_MIN, -10) {
                    local preearly_main `preearly_main' geo_main_`suffix'
                    local preearly_rest `preearly_rest' geo_rest_`suffix'
                }
                if inrange(`k', -10, -2) {
                    local prerecent_main `prerecent_main' geo_main_`suffix'
                    local prerecent_rest `prerecent_rest' geo_rest_`suffix'
                }
            }
        }

        reghdfe `outcome' `all', ///
            absorb(unit_id province_ym cno1_ym) vce(cluster cno4_id)
        local observations = e(N)
        local clusters = e(N_clust)

        postfile E str40 specification str32 outcome byte group_id ///
            str24 geographic_group int event_time ///
            double estimate se ci_low ci_high long observations clusters ///
            using `event_results', replace
        forvalues k = $ES_MIN/$ES_MAX {
            if `k' < 0 local suffix "m`=abs(`k')'"
            else local suffix "p`k'"
            local present : list posof "`k'" in observed_event_values
            foreach group in main rest {
                if "`group'" == "main" {
                    local group_id 1
                    local group_label "Madrid and Barcelona"
                }
                else {
                    local group_id 2
                    local group_label "Rest of Spain"
                }
                if `present' == 0 {
                    post E ("`specification'") ("`outcome'") ///
                        (`group_id') ("`group_label'") (`k') ///
                        (.) (.) (.) (.) (`observations') (`clusters')
                }
                else if `k' == -1 {
                    post E ("`specification'") ("`outcome'") ///
                        (`group_id') ("`group_label'") (`k') ///
                        (0) (0) (0) (0) (`observations') (`clusters')
                }
                else {
                    local b = _b[geo_`group'_`suffix']
                    local s = _se[geo_`group'_`suffix']
                    post E ("`specification'") ("`outcome'") ///
                        (`group_id') ("`group_label'") (`k') ///
                        (`b') (`s') (`b' - 1.96*`s') (`b' + 1.96*`s') ///
                        (`observations') (`clusters')
                }
            }
        }
        postclose E

        postfile P str40 specification str32 outcome str24 geographic_group ///
            str16 window str32 test double F_stat df_num df_den p_value ///
            long observations clusters using `pretrend_results', replace
        foreach group in main rest {
            if "`group'" == "main" local group_label "Madrid and Barcelona"
            else local group_label "Rest of Spain"
            foreach window in full_-21_-2 early_-21_-10 recent_-10_-2 {
                if "`group'" == "main" {
                    if "`window'" == "full_-21_-2" local variables `prefull_main'
                    else if "`window'" == "early_-21_-10" local variables `preearly_main'
                    else local variables `prerecent_main'
                }
                else {
                    if "`window'" == "full_-21_-2" local variables `prefull_rest'
                    else if "`window'" == "early_-21_-10" local variables `preearly_rest'
                    else local variables `prerecent_rest'
                }

                local npre : word count `variables'
                if `npre' >= 2 {
                    test `variables'
                    post P ("`specification'") ("`outcome'") ///
                        ("`group_label'") ("`window'") ("joint_equal_zero") ///
                        (r(F)) (r(df)) (r(df_r)) (r(p)) (e(N)) (e(N_clust))
                    local first : word 1 of `variables'
                    local restrictions
                    forvalues j = 2/`npre' {
                        local variable : word `j' of `variables'
                        local restrictions `restrictions' (`variable' = `first')
                    }
                    test `restrictions'
                    post P ("`specification'") ("`outcome'") ///
                        ("`group_label'") ("`window'") ///
                        ("joint_equal_coefficients") ///
                        (r(F)) (r(df)) (r(df_r)) (r(p)) (e(N)) (e(N_clust))
                }
            }
        }
        postclose P

        gen double dose_adjustment_main = exposure_10pp * ///
            inrange(event_time, 0, 24) * main_province
        gen double dose_adjustment_rest = exposure_10pp * ///
            inrange(event_time, 0, 24) * (1 - main_province)
        gen double dose_later_main = exposure_10pp * ///
            inrange(event_time, 25, 40) * main_province
        gen double dose_later_rest = exposure_10pp * ///
            inrange(event_time, 25, 40) * (1 - main_province)

        reghdfe `outcome' dose_adjustment_main dose_adjustment_rest ///
            dose_later_main dose_later_rest, ///
            absorb(unit_id province_ym cno1_ym) vce(cluster cno4_id)
        local observations = e(N)
        local clusters = e(N_clust)
        test dose_adjustment_main = dose_adjustment_rest
        local between_adjustment = r(p)
        test dose_later_main = dose_later_rest
        local between_later = r(p)
        test dose_adjustment_main = dose_later_main
        local phase_main = r(p)
        test dose_adjustment_rest = dose_later_rest
        local phase_rest = r(p)

        quietly count if main_province == 1 & !missing(`outcome')
        local observations_main = r(N)
        quietly count if main_province == 0 & !missing(`outcome')
        local observations_rest = r(N)

        postfile Q str40 specification str32 outcome byte group_id ///
            str24 geographic_group str16 phase int event_start event_end ///
            double estimate se ci_low ci_high effect_percent ///
            phase_equality_p between_group_p long observations clusters ///
            using `phase_results', replace
        foreach group in main rest {
            if "`group'" == "main" {
                local group_id 1
                local group_label "Madrid and Barcelona"
                local group_observations `observations_main'
                local phase_p `phase_main'
            }
            else {
                local group_id 2
                local group_label "Rest of Spain"
                local group_observations `observations_rest'
                local phase_p `phase_rest'
            }
            foreach phase in adjustment later {
                if "`phase'" == "adjustment" {
                    local variable dose_adjustment_`group'
                    local start 0
                    local end 24
                    local between_p `between_adjustment'
                }
                else {
                    local variable dose_later_`group'
                    local start 25
                    local end 40
                    local between_p `between_later'
                }
                lincom `variable'
                post Q ("`specification'") ("`outcome'") ///
                    (`group_id') ("`group_label'") ("`phase'") (`start') (`end') ///
                    (r(estimate)) (r(se)) (r(lb)) (r(ub)) ///
                    (100*r(estimate)) (`phase_p') (`between_p') ///
                    (`group_observations') (`clusters')
            }
        }
        postclose Q

        use `event_results', clear
        sort group_id event_time
        export delimited using ///
            "$TAB/twfe_event_mainprovince_comparison`file_suffix'_`outcome'.csv", replace
        use `pretrend_results', clear
        sort geographic_group window test
        export delimited using ///
            "$TAB/twfe_pretrend_mainprovince_comparison`file_suffix'_`outcome'.csv", replace
        use `phase_results', clear
        sort group_id phase
        export delimited using ///
            "$TAB/twfe_phase_mainprovince_comparison`file_suffix'_`outcome'.csv", replace
    restore
end



capture program drop produce_main_province_outputs
program define produce_main_province_outputs
    display as result ///
        "Running Madrid-and-Barcelona versus rest-of-Spain heterogeneity"
    load_v1_panel using "$IN/est_province_cno4.csv"
    foreach outcome in ln_parados ln_contratos {
        run_main_province_comparison, outcome(`outcome')
        run_main_province_comparison, outcome(`outcome') no2021
    }
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
    load_v1_panel using "$IN/est_feminization_cno4.csv"
    gen byte sample_from_2022 = ym_stata >= tm(2022m1)
    foreach outcome in ln_parados ln_contratos {
        run_feminization_median_phase, outcome(`outcome')
        run_feminization_median_event, outcome(`outcome')
        run_feminization_median_phase, outcome(`outcome') ///
            samplevar(sample_from_2022) filesuffix(no2021)
        run_feminization_median_event, outcome(`outcome') ///
            samplevar(sample_from_2022) filesuffix(no2021)
    }

    prep_fem_detrended
    foreach outcome in ln_parados ln_contratos {
        run_feminization_median_event, outcome(`outcome'_detrended) detrended
    }
end
