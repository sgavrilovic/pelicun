# -*- coding: utf-8 -*-
#
# Copyright (c) 2018 Leland Stanford Junior University
# Copyright (c) 2018 The Regents of the University of California
#
# This file is part of pelicun.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# You should have received a copy of the BSD 3-Clause License along with
# pelicun. If not, see <http://www.opensource.org/licenses/>.
#
# Contributors:
# Adam Zsarnóczay

"""
This subpackage performs system tests on the control module of pelicun.

"""

import pytest
import numpy as np
from numpy.testing import assert_allclose
from scipy.stats import truncnorm as tnorm
from copy import deepcopy

import os, sys, inspect
current_dir = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0,os.path.dirname(parent_dir))

from pelicun.control import *
from pelicun.uq import mvn_orthotope_density as mvn_od
from pelicun.tests.test_pelicun import prob_allclose, prob_approx

# -----------------------------------------------------------------------------
# FEMA_P58_Assessment
# -----------------------------------------------------------------------------

def test_FEMA_P58_Assessment_central_tendencies():
    """
    Perform a loss assessment with customized inputs that reduce the
    dispersion of calculation parameters to negligible levels. This allows us
    to test the results against pre-defined reference values in spite of the
    randomness involved in the calculations.

    """

    base_input_path = 'resources/'
    DL_input = base_input_path + 'input data/' + "DL_input_test.json"
    EDP_input = base_input_path + 'EDP data/' + "EDP_table_test.out"

    A = FEMA_P58_Assessment()

    A.read_inputs(DL_input, EDP_input, verbose=False)

    A.define_random_variables()

    # -------------------------------------------------- check random variables

    # EDP
    RV_EDP = A._RV_dict['EDP']
    assert RV_EDP.theta == pytest.approx(0.5 * g)
    assert RV_EDP.COV == pytest.approx(0., abs=1e-10)
    assert RV_EDP._distribution_kind == 'lognormal'

    # QNT
    RV_QNT = A._RV_dict['QNT']
    assert RV_QNT is None

    # FRG
    RV_FRG = A._RV_dict['FR-T0001.001']
    assert_allclose(RV_FRG.theta, np.array([0.37, 0.5, 0.82]) * g, rtol=0.01)
    COV = deepcopy(RV_FRG.COV)
    sig = np.sqrt(np.diagonal(COV))
    assert_allclose(sig, np.array([0.3, 0.4, 0.5]), rtol=0.01)
    assert_allclose(COV / np.outer(sig, sig), np.ones((3, 3)), rtol=0.01)
    for dist in RV_FRG._distribution_kind:
        assert dist == 'lognormal'

    # RED
    RV_RED = A._RV_dict['DV_RED']
    assert_allclose(RV_RED.theta, np.ones(2), rtol=0.01)
    assert_allclose(RV_RED.COV, np.array([[1, 0], [0, 1]]) * (1e-4) ** 2.,
                    rtol=0.01)
    assert RV_RED._distribution_kind == 'normal'
    assert RV_RED.tr_limits_pre == None
    assert_allclose(RV_RED.tr_limits_post[0], np.array([0., 0.]),
                    rtol=0.01)
    assert_allclose(RV_RED.tr_limits_post[1], np.array([2., 4.]),
                    rtol=0.01)

    # INJ
    RV_INJ = A._RV_dict['DV_INJ']
    assert_allclose(RV_INJ.theta, np.ones(4), rtol=0.01)
    COV = deepcopy(RV_INJ.COV)
    sig = np.sqrt(np.diagonal(COV))
    assert_allclose(sig, np.ones(4) * (1e-4), rtol=0.01)
    rho_target = np.zeros((4, 4))
    np.fill_diagonal(rho_target, 1.)
    assert_allclose(COV / np.outer(sig, sig), rho_target, rtol=0.01)
    assert RV_INJ._distribution_kind == 'normal'
    assert RV_INJ.tr_limits_pre == None
    assert_allclose(RV_INJ.tr_limits_post,
                    np.array([[0., 0., 0., 0.],
                              [10 / 3., 10 / 3., 10., 10.]]), rtol=0.01)

    # REP
    RV_REP = A._RV_dict['DV_REP']
    assert_allclose(RV_REP.theta, np.ones(6), rtol=0.01)
    COV = deepcopy(RV_REP.COV)
    sig = np.sqrt(np.diagonal(COV))
    assert_allclose(sig, np.ones(6) * (1e-4), rtol=0.01)
    rho_target = np.zeros((6, 6))
    np.fill_diagonal(rho_target, 1.)
    assert_allclose(COV / np.outer(sig, sig), rho_target, rtol=0.01)
    for dist in RV_REP._distribution_kind:
        assert dist == 'lognormal'

    # ------------------------------------------------------------------------

    A.define_loss_model()

    # QNT (deterministic)
    QNT = A._FG_dict['T0001.001']._performance_groups[0]._quantity
    assert QNT == pytest.approx(50., rel=0.01)

    A.calculate_damage()

    # ------------------------------------------------ check damage calculation
    # TIME
    T_check = A._TIME.describe().T.loc[['hour','month','weekday?'],:]

    assert_allclose(T_check['mean'], np.array([11.5, 5.5, 5. / 7.]), rtol=0.05)
    assert_allclose(T_check['min'], np.array([0., 0., 0.]), rtol=0.01)
    assert_allclose(T_check['max'], np.array([23., 11., 1.]), rtol=0.01)
    assert_allclose(T_check['50%'], np.array([12., 5., 1.]), atol=1.0)
    assert_allclose(T_check['count'], np.array([10000., 10000., 10000.]),
                    rtol=0.01)

    # POP
    P_CDF = A._POP.describe(np.arange(1, 27) / 27.).iloc[:, 0].values[4:]
    vals, counts = np.unique(P_CDF, return_counts=True)
    assert_allclose(vals, np.array([0., 2.5, 5., 10.]), rtol=0.01)
    assert_allclose(counts, np.array([14, 2, 7, 5]), atol=1)

    # COL
    COL_check = A._COL.describe().T
    assert COL_check['mean'].values[0] == pytest.approx(0.5, rel=0.05)
    assert len(A._ID_dict['non-collapse']) == pytest.approx(5000, rel=0.05)
    assert len(A._ID_dict['collapse']) == pytest.approx(5000, rel=0.05)

    # DMG
    DMG_check = A._DMG.describe().T
    assert_allclose(DMG_check['mean'], np.array([17.074, 17.074, 7.9361]),
                    rtol=0.1, atol=1.0)
    assert_allclose(DMG_check['min'], np.zeros(3), rtol=0.01)
    assert_allclose(DMG_check['max'], np.ones(3) * 50.0157, rtol=0.05)

    # ------------------------------------------------------------------------

    A.calculate_losses()

    # -------------------------------------------------- check loss calculation

    # RED
    DV_RED = A._DV_dict['red_tag'].describe().T
    assert_allclose(DV_RED['mean'], np.array([0.341344, 0.1586555]), rtol=0.1)

    # INJ - collapse
    DV_INJ_C = deepcopy(A._COL[['INJ-0', 'INJ-1']])
    DV_INJ_C.dropna(inplace=True)
    NC_count = DV_INJ_C.describe().T['count'][0]
    assert_allclose(NC_count, np.ones(2) * 5000, rtol=0.05)
    # lvl 1
    vals, counts = np.unique(DV_INJ_C.iloc[:, 0].values, return_counts=True)
    assert_allclose(vals, np.array([0., 2.5, 5., 10.]) * 0.1, rtol=0.01)
    assert_allclose(counts / NC_count, np.array([14, 2, 7, 5]) / 28., atol=0.01, rtol=0.1)
    # lvl 2
    vals, counts = np.unique(DV_INJ_C.iloc[:, 1].values, return_counts=True)
    assert_allclose(vals, np.array([0., 2.5, 5., 10.]) * 0.9, rtol=0.01)
    assert_allclose(counts / NC_count, np.array([14, 2, 7, 5]) / 28., atol=0.01, rtol=0.1)

    # INJ - non-collapse
    DV_INJ_NC = deepcopy(A._DV_dict['injuries'])
    DV_INJ_NC[0].dropna(inplace=True)
    assert_allclose(DV_INJ_NC[0].describe().T['count'], np.ones(2) * 5000,
                    rtol=0.05)
    # lvl 1 DS2
    I_CDF = DV_INJ_NC[0].iloc[:, 0]
    I_CDF = np.around(I_CDF, decimals=3)
    vals, counts = np.unique(I_CDF, return_counts=True)
    assert_allclose(vals, np.array([0., 0.075, 0.15, 0.3]), rtol=0.01)
    target_prob = np.array(
        [0.6586555, 0., 0., 0.] + 0.3413445 * np.array([14, 2, 7, 5]) / 28.)
    assert_allclose(counts / NC_count, target_prob, atol=0.01, rtol=0.1)
    # lvl 1 DS3
    I_CDF = DV_INJ_NC[0].iloc[:, 1]
    I_CDF = np.around(I_CDF, decimals=3)
    vals, counts = np.unique(I_CDF, return_counts=True)
    assert_allclose(vals, np.array([0., 0.075, 0.15, 0.3]), rtol=0.01)
    target_prob = np.array(
        [0.8413445, 0., 0., 0.] + 0.1586555 * np.array([14, 2, 7, 5]) / 28.)
    assert_allclose(counts / NC_count, target_prob, atol=0.01, rtol=0.1)
    # lvl 2 DS2
    I_CDF = DV_INJ_NC[1].iloc[:, 0]
    I_CDF = np.around(I_CDF, decimals=3)
    vals, counts = np.unique(I_CDF, return_counts=True)
    assert_allclose(vals, np.array([0., 0.025, 0.05, 0.1]), rtol=0.01)
    target_prob = np.array(
        [0.6586555, 0., 0., 0.] + 0.3413445 * np.array([14, 2, 7, 5]) / 28.)
    assert_allclose(counts / NC_count, target_prob, atol=0.01, rtol=0.1)
    # lvl2 DS3
    I_CDF = DV_INJ_NC[1].iloc[:, 1]
    I_CDF = np.around(I_CDF, decimals=3)
    vals, counts = np.unique(I_CDF, return_counts=True)
    assert_allclose(vals, np.array([0., 0.025, 0.05, 0.1]), rtol=0.01)
    target_prob = np.array(
        [0.8413445, 0., 0., 0.] + 0.1586555 * np.array([14, 2, 7, 5]) / 28.)
    assert_allclose(counts / NC_count, target_prob, atol=0.01, rtol=0.1)

    # REP
    assert len(A._ID_dict['non-collapse']) == len(A._ID_dict['repairable'])
    assert len(A._ID_dict['irreparable']) == 0
    # cost
    DV_COST = A._DV_dict['rec_cost']
    # DS1
    C_CDF = DV_COST.iloc[:, 0]
    C_CDF = np.around(C_CDF / 10., decimals=0) * 10.
    vals, counts = np.unique(C_CDF, return_counts=True)
    assert_allclose(vals, [0, 2500], rtol=0.01)
    t_prob = 0.3413445
    assert_allclose(counts / NC_count, [1. - t_prob, t_prob], rtol=0.1)
    # DS2
    C_CDF = DV_COST.iloc[:, 1]
    C_CDF = np.around(C_CDF / 100., decimals=0) * 100.
    vals, counts = np.unique(C_CDF, return_counts=True)
    assert_allclose(vals, [0, 25000], rtol=0.01)
    t_prob = 0.3413445
    assert_allclose(counts / NC_count, [1. - t_prob, t_prob], rtol=0.1)
    # DS3
    C_CDF = DV_COST.iloc[:, 2]
    C_CDF = np.around(C_CDF / 1000., decimals=0) * 1000.
    vals, counts = np.unique(C_CDF, return_counts=True)
    assert_allclose(vals, [0, 250000], rtol=0.01)
    t_prob = 0.1586555
    assert_allclose(counts / NC_count, [1. - t_prob, t_prob], rtol=0.1)
    # time
    DV_TIME = A._DV_dict['rec_time']
    # DS1
    T_CDF = DV_TIME.iloc[:, 0]
    T_CDF = np.around(T_CDF, decimals=1)
    vals, counts = np.unique(T_CDF, return_counts=True)
    assert_allclose(vals, [0, 2.5], rtol=0.01)
    t_prob = 0.3413445
    assert_allclose(counts / NC_count, [1. - t_prob, t_prob], rtol=0.1)
    # DS2
    T_CDF = DV_TIME.iloc[:, 1]
    T_CDF = np.around(T_CDF, decimals=0)
    vals, counts = np.unique(T_CDF, return_counts=True)
    assert_allclose(vals, [0, 25], rtol=0.01)
    t_prob = 0.3413445
    assert_allclose(counts / NC_count, [1. - t_prob, t_prob], rtol=0.1)
    # DS3
    T_CDF = DV_TIME.iloc[:, 2]
    T_CDF = np.around(T_CDF / 10., decimals=0) * 10.
    vals, counts = np.unique(T_CDF, return_counts=True)
    assert_allclose(vals, [0, 250], rtol=0.01)
    t_prob = 0.1586555
    assert_allclose(counts / NC_count, [1. - t_prob, t_prob], rtol=0.1)

    # ------------------------------------------------------------------------

    A.aggregate_results()

    # ------------------------------------------------ check result aggregation

    S = A._SUMMARY
    SD = S.describe().T

    assert_allclose(S[('event time', 'month')], A._TIME['month'] + 1)
    assert_allclose(S[('event time', 'weekday?')], A._TIME['weekday?'])
    assert_allclose(S[('event time', 'hour')], A._TIME['hour'])
    assert_allclose(S[('inhabitants', '')], A._POP.iloc[:, 0])

    assert SD.loc[('collapses', 'collapsed'), 'mean'] == pytest.approx(0.5,
                                                                        rel=0.05)
    assert SD.loc[('collapses', 'mode'), 'mean'] == 0.
    assert SD.loc[('collapses', 'mode'), 'count'] == pytest.approx(5000,
                                                                   rel=0.05)

    assert SD.loc[('red tagged', ''), 'mean'] == pytest.approx(0.5, rel=0.05)
    assert SD.loc[('red tagged', ''), 'count'] == pytest.approx(5000, rel=0.05)

    for col in ['irreparable', 'cost impractical', 'time impractical']:
        assert SD.loc[('reconstruction', col), 'mean'] == 0.
        assert SD.loc[('reconstruction', col), 'count'] == pytest.approx(5000,
                                                                         rel=0.05)

    RC = deepcopy(S.loc[:, ('reconstruction', 'cost')])
    RC_CDF = np.around(RC / 1000., decimals=0) * 1000.
    vals, counts = np.unique(RC_CDF, return_counts=True)
    assert_allclose(vals, np.array([0, 2., 3., 25., 250., 300.]) * 1000.)
    t_prob1 = 0.3413445 / 2.
    t_prob2 = 0.1586555 / 2.
    assert_allclose(counts / 10000.,
                    [t_prob2, t_prob1 / 2., t_prob1 / 2., t_prob1, t_prob2,
                     0.5], atol=0.01, rtol=0.1)

    RT = deepcopy(S.loc[:, ('reconstruction', 'time-parallel')])
    RT_CDF = np.around(RT, decimals=0)
    vals, counts = np.unique(RT_CDF, return_counts=True)
    assert_allclose(vals, np.array([0, 2., 3., 25., 250., 300.]))
    t_prob1 = 0.3413445 / 2.
    t_prob2 = 0.1586555 / 2.
    assert_allclose(counts / 10000.,
                    [t_prob2, t_prob1 / 2., t_prob1 / 2., t_prob1, t_prob2,
                     0.5], atol=0.01, rtol=0.1)

    assert_allclose(S.loc[:, ('reconstruction', 'time-parallel')],
                    S.loc[:, ('reconstruction', 'time-sequential')])

    CAS = deepcopy(S.loc[:, ('injuries', 'sev1')])
    CAS_CDF = np.around(CAS, decimals=3)
    vals, counts = np.unique(CAS_CDF, return_counts=True)
    assert_allclose(vals, [0, 0.075, 0.15, 0.25, 0.3, 0.5, 1.])
    assert_allclose(counts / 10000.,
                    np.array([35, 1, 3.5, 2, 2.5, 7, 5]) / 56., atol=0.01,
                    rtol=0.1)

    CAS = deepcopy(S.loc[:, ('injuries', 'sev2')])
    CAS_CDF = np.around(CAS, decimals=3)
    vals, counts = np.unique(CAS_CDF, return_counts=True)
    assert_allclose(vals, [0, 0.025, 0.05, 0.1, 2.25, 4.5, 9.])
    assert_allclose(counts / 10000.,
                    np.array([35, 1, 3.5, 2.5, 2, 7, 5]) / 56., atol=0.01,
                    rtol=0.1)


def test_FEMA_P58_Assessment_EDP_uncertainty_basic():
    """
    Perform a loss assessment with customized inputs that focus on testing the
    methods used to estimate the multivariate lognormal distribution of EDP
    values. Besides the fitting, this test also evaluates the propagation of
    EDP uncertainty through the analysis. Dispersions in other calculation
    parameters are reduced to negligible levels. This allows us to test the
    results against pre-defined reference values in spite of the  randomness
    involved in the calculations.
    """

    base_input_path = 'resources/'
    DL_input = base_input_path + 'input data/' + "DL_input_test_2.json"
    EDP_input = base_input_path + 'EDP data/' + "EDP_table_test_2.out"

    A = FEMA_P58_Assessment()

    A.read_inputs(DL_input, EDP_input, verbose=False)

    A.define_random_variables()

    # -------------------------------------------------- check random variables

    # EDP
    RV_EDP = A._RV_dict['EDP']
    assert RV_EDP._distribution_kind == 'lognormal'
    assert_allclose(RV_EDP.theta, [9.80665, 12.59198, 0.074081, 0.044932],
                    rtol=0.05)
    COV = deepcopy(RV_EDP.COV)
    sig = np.sqrt(np.diagonal(COV))
    assert_allclose(sig, [0.25, 0.25, 0.3, 0.4], rtol=0.1)
    rho_target = [
        [1.0, 0.6, 0.3, 0.3],
        [0.6, 1.0, 0.3, 0.3],
        [0.3, 0.3, 1.0, 0.7],
        [0.3, 0.3, 0.7, 1.0]]
    assert_allclose(COV / np.outer(sig, sig), rho_target, atol=0.1)

    # ------------------------------------------------------------------------

    A.define_loss_model()

    A.calculate_damage()

    # ------------------------------------------------ check damage calculation
    # COL
    COL_check = A._COL.describe().T
    col_target = 1.0 - mvn_od(np.log([0.074081, 0.044932]),
                              np.array([[1, 0.7], [0.7, 1]]) * np.outer(
                                  [0.3, 0.4], [0.3, 0.4]),
                              upper=np.log([0.1, 0.1]))[0]
    assert COL_check['mean'].values[0] == pytest.approx(col_target, rel=0.1)

    # DMG
    DMG_check = [len(np.where(A._DMG.iloc[:, i] > 0.0)[0]) / 10000. for i in
                 range(8)]

    DMG_1_PID = mvn_od(np.log([0.074081, 0.044932]),
                       np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                                 [0.3, 0.4]),
                       lower=np.log([0.05488, 1e-6]), upper=np.log([0.1, 0.1]))[
        0]
    DMG_2_PID = mvn_od(np.log([0.074081, 0.044932]),
                       np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                                 [0.3, 0.4]),
                       lower=np.log([1e-6, 0.05488]), upper=np.log([0.1, 0.1]))[
        0]
    DMG_1_PFA = mvn_od(np.log([0.074081, 9.80665]),
                       np.array([[1, 0.3], [0.3, 1]]) * np.outer([0.3, 0.25],
                                                                 [0.3, 0.25]),
                       lower=np.log([1e-6, 9.80665]),
                       upper=np.log([0.1, np.inf]))[0]
    DMG_2_PFA = mvn_od(np.log([0.074081, 12.59198]),
                       np.array([[1, 0.3], [0.3, 1]]) * np.outer([0.3, 0.25],
                                                                 [0.3, 0.25]),
                       lower=np.log([1e-6, 9.80665]),
                       upper=np.log([0.1, np.inf]))[0]

    assert DMG_check[0] == pytest.approx(DMG_check[1], rel=0.01)
    assert DMG_check[2] == pytest.approx(DMG_check[3], rel=0.01)
    assert DMG_check[4] == pytest.approx(DMG_check[5], rel=0.01)
    assert DMG_check[6] == pytest.approx(DMG_check[7], rel=0.01)

    assert DMG_check[0] == pytest.approx(DMG_1_PID, rel=0.10)
    assert DMG_check[2] == pytest.approx(DMG_2_PID, rel=0.10)
    assert DMG_check[4] == pytest.approx(DMG_1_PFA, rel=0.10)
    assert DMG_check[6] == pytest.approx(DMG_2_PFA, rel=0.10)

    # ------------------------------------------------------------------------

    A.calculate_losses()

    # -------------------------------------------------- check loss calculation
    # COST
    DV_COST = A._DV_dict['rec_cost']
    DV_TIME = A._DV_dict['rec_time']

    C_target = [0., 250., 1250.]
    T_target = [0., 0.25, 1.25]

    # PG 1011 and 1012
    P_target = [
        mvn_od(np.log([0.074081, 0.044932]),
               np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                         [0.3, 0.4]),
               lower=np.log([1e-6, 1e-6]), upper=np.log([0.05488, 0.1]))[0],
        mvn_od(np.log([0.074081, 0.044932]),
               np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                         [0.3, 0.4]),
               lower=np.log([0.05488, 0.05488]), upper=np.log([0.1, 0.1]))[0],
        mvn_od(np.log([0.074081, 0.044932]),
               np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                         [0.3, 0.4]),
               lower=np.log([0.05488, 1e-6]), upper=np.log([0.1, 0.05488]))[0],
    ]

    for i in [0, 1]:
        C_test, P_test = np.unique(
            np.around(DV_COST.iloc[:, i].values / 10., decimals=0) * 10.,
            return_counts=True)
        C_test = C_test[np.where(P_test > 10)]
        T_test, P_test = np.unique(
            np.around(DV_TIME.iloc[:, i].values * 100., decimals=0) / 100.,
            return_counts=True)
        T_test = T_test[np.where(P_test > 10)]
        P_test = P_test[np.where(P_test > 10)]
        P_test = P_test / 10000.

        assert_allclose(P_target, P_test, atol=0.02)
        assert_allclose(C_target, C_test, rtol=0.001)
        assert_allclose(T_target, T_test, rtol=0.001)

    # PG 1021 and 1022
    P_target = [
        mvn_od(np.log([0.074081, 0.044932]),
               np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                         [0.3, 0.4]),
               lower=np.log([1e-6, 1e-6]), upper=np.log([0.1, 0.05488]))[0],
        mvn_od(np.log([0.074081, 0.044932]),
               np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                         [0.3, 0.4]),
               lower=np.log([0.05488, 0.05488]), upper=np.log([0.1, 0.1]))[0],
        mvn_od(np.log([0.074081, 0.044932]),
               np.array([[1, 0.7], [0.7, 1]]) * np.outer([0.3, 0.4],
                                                         [0.3, 0.4]),
               lower=np.log([1e-6, 0.05488]), upper=np.log([0.05488, 0.1]))[0],
    ]

    for i in [2, 3]:
        C_test, P_test = np.unique(
            np.around(DV_COST.iloc[:, i].values / 10., decimals=0) * 10.,
            return_counts=True)
        C_test = C_test[np.where(P_test > 10)]
        T_test, P_test = np.unique(
            np.around(DV_TIME.iloc[:, i].values * 100., decimals=0) / 100.,
            return_counts=True)
        T_test = T_test[np.where(P_test > 10)]
        P_test = P_test[np.where(P_test > 10)]
        P_test = P_test / 10000.

        assert_allclose(P_target, P_test, atol=0.02)
        assert_allclose(C_target, C_test, rtol=0.001)
        assert_allclose(T_target, T_test, rtol=0.001)

    # PG 2011 and 2012
    P_target = [
        mvn_od(np.log([0.074081, 9.80665, 12.59198]),
               np.array([[1.0, 0.3, 0.3], [0.3, 1.0, 0.6],
                         [0.3, 0.6, 1.0]]) * np.outer([0.3, 0.25, 0.25],
                                                      [0.3, 0.25, 0.25]),
               lower=np.log([1e-6, 1e-6, 1e-6]),
               upper=np.log([0.1, 9.80665, np.inf]))[0],
        mvn_od(np.log([0.074081, 9.80665, 12.59198]),
               np.array([[1.0, 0.3, 0.3], [0.3, 1.0, 0.6],
                         [0.3, 0.6, 1.0]]) * np.outer([0.3, 0.25, 0.25],
                                                      [0.3, 0.25, 0.25]),
               lower=np.log([1e-6, 9.80665, 9.80665]),
               upper=np.log([0.1, np.inf, np.inf]))[0],
        mvn_od(np.log([0.074081, 9.80665, 12.59198]),
               np.array([[1.0, 0.3, 0.3], [0.3, 1.0, 0.6],
                         [0.3, 0.6, 1.0]]) * np.outer([0.3, 0.25, 0.25],
                                                      [0.3, 0.25, 0.25]),
               lower=np.log([1e-6, 9.80665, 1e-6]),
               upper=np.log([0.1, np.inf, 9.80665]))[0],
    ]

    for i in [4, 5]:
        C_test, P_test = np.unique(
            np.around(DV_COST.iloc[:, i].values / 10., decimals=0) * 10.,
            return_counts=True)
        C_test = C_test[np.where(P_test > 10)]
        T_test, P_test = np.unique(
            np.around(DV_TIME.iloc[:, i].values * 100., decimals=0) / 100.,
            return_counts=True)
        T_test = T_test[np.where(P_test > 10)]
        P_test = P_test[np.where(P_test > 10)]
        P_test = P_test / 10000.

        assert_allclose(P_target, P_test, atol=0.02)
        assert_allclose(C_target, C_test, rtol=0.001)
        assert_allclose(T_target, T_test, rtol=0.001)

    # PG 2021 and 2022
    P_target = [
        mvn_od(np.log([0.074081, 9.80665, 12.59198]),
               np.array([[1.0, 0.3, 0.3], [0.3, 1.0, 0.6],
                         [0.3, 0.6, 1.0]]) * np.outer([0.3, 0.25, 0.25],
                                                      [0.3, 0.25, 0.25]),
               lower=np.log([1e-6, 1e-6, 1e-6]),
               upper=np.log([0.1, np.inf, 9.80665]))[0],
        mvn_od(np.log([0.074081, 9.80665, 12.59198]),
               np.array([[1.0, 0.3, 0.3], [0.3, 1.0, 0.6],
                         [0.3, 0.6, 1.0]]) * np.outer([0.3, 0.25, 0.25],
                                                      [0.3, 0.25, 0.25]),
               lower=np.log([1e-6, 9.80665, 9.80665]),
               upper=np.log([0.1, np.inf, np.inf]))[0],
        mvn_od(np.log([0.074081, 9.80665, 12.59198]),
               np.array([[1.0, 0.3, 0.3], [0.3, 1.0, 0.6],
                         [0.3, 0.6, 1.0]]) * np.outer([0.3, 0.25, 0.25],
                                                      [0.3, 0.25, 0.25]),
               lower=np.log([1e-6, 1e-6, 9.80665]),
               upper=np.log([0.1, 9.80665, np.inf]))[0],
    ]

    for i in [6, 7]:
        C_test, P_test = np.unique(
            np.around(DV_COST.iloc[:, i].values / 10., decimals=0) * 10.,
            return_counts=True)
        C_test = C_test[np.where(P_test > 10)]
        T_test, P_test = np.unique(
            np.around(DV_TIME.iloc[:, i].values * 100., decimals=0) / 100.,
            return_counts=True)
        T_test = T_test[np.where(P_test > 10)]
        P_test = P_test[np.where(P_test > 10)]
        P_test = P_test / 10000.

        assert_allclose(P_target, P_test, atol=0.02)
        assert_allclose(C_target, C_test, rtol=0.001)
        assert_allclose(T_target, T_test, rtol=0.001)

    # RED TAG
    RED_check = A._DV_dict['red_tag'].describe().T
    RED_check = (RED_check['mean'] * RED_check['count'] / 10000.).values

    assert RED_check[0] == pytest.approx(RED_check[1], rel=0.01)
    assert RED_check[2] == pytest.approx(RED_check[3], rel=0.01)
    assert RED_check[4] == pytest.approx(RED_check[5], rel=0.01)
    assert RED_check[6] == pytest.approx(RED_check[7], rel=0.01)

    assert RED_check[0] == pytest.approx(DMG_1_PID, rel=0.10)
    assert RED_check[2] == pytest.approx(DMG_2_PID, rel=0.10)
    assert RED_check[4] == pytest.approx(DMG_1_PFA, rel=0.10)
    assert RED_check[6] == pytest.approx(DMG_2_PFA, rel=0.10)

    DMG_on = np.where(A._DMG > 0.0)[0]
    RED_on = np.where(A._DV_dict['red_tag'] > 0.0)[0]
    assert_allclose(DMG_on, RED_on)

    # ------------------------------------------------------------------------

    A.aggregate_results()

    # ------------------------------------------------ check result aggregation

    P_no_RED_target = mvn_od(np.log([0.074081, 0.044932, 9.80665, 12.59198]),
                             np.array(
                                 [[1.0, 0.7, 0.3, 0.3], [0.7, 1.0, 0.3, 0.3],
                                  [0.3, 0.3, 1.0, 0.6],
                                  [0.3, 0.3, 0.6, 1.0]]) * np.outer(
                                 [0.3, 0.4, 0.25, 0.25],
                                 [0.3, 0.4, 0.25, 0.25]),
                             lower=np.log([1e-6, 1e-6, 1e-6, 1e-6]),
                             upper=np.log(
                                 [0.05488, 0.05488, 9.80665, 9.80665]))[0]
    S = A._SUMMARY
    SD = S.describe().T

    P_no_RED_test = (1.0 - SD.loc[('red tagged', ''), 'mean']) * SD.loc[
        ('red tagged', ''), 'count'] / 10000.



