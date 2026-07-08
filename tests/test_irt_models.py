"""IRT 多级评分模型测试（差距项 #3）。"""

import numpy as np
import pytest

from engines.irt_models import (
    GPCM, GRM, select_model, compute_fit_indices,
    _HAS_NUMBA_IRT,
)


class TestGPCM:
    """GPCM 模型测试。"""

    @pytest.fixture
    def gpcm(self) -> GPCM:
        return GPCM(n_categories=4)

    def test_prob_returns_correct_shape(self, gpcm: GPCM) -> None:
        probs = gpcm.prob(0.0, alpha=1.5, deltas=np.array([-1.0, 0.0, 1.0, 2.0]))
        assert len(probs) == 4
        assert abs(np.sum(probs) - 1.0) < 1e-6

    def test_prob_sum_to_one(self, gpcm: GPCM) -> None:
        for theta in [-3, -1, 0, 1, 3]:
            probs = gpcm.prob(theta, alpha=1.0, deltas=np.array([-1.0, 0.0, 1.0]))
            assert abs(np.sum(probs) - 1.0) < 1e-6, f"theta={theta}"

    def test_information_positive(self, gpcm: GPCM) -> None:
        info = gpcm.information(0.0, alpha=1.0, deltas=np.array([-1.0, 0.0, 1.0]))
        assert info > 0

    def test_prob_matrix_shape(self, gpcm: GPCM) -> None:
        thetas = np.linspace(-3, 3, 10)
        probs = gpcm.prob_matrix(thetas, alpha=1.0, deltas=np.array([-1.0, 0.0, 1.0, 2.0]))
        assert probs.shape == (10, 4)

    def test_eap_estimate(self, gpcm: GPCM) -> None:
        responses = np.array([2, 1, 3])  # 模拟作答
        theta, se = gpcm.eap_estimate(responses, alpha=1.0, deltas=np.array([-1.0, 0.0, 1.0, 2.0]))
        assert isinstance(theta, float)
        assert se > 0

    def test_log_likelihood_negative(self, gpcm: GPCM) -> None:
        responses = np.array([2, 1, 3])
        ll = gpcm.log_likelihood(responses, alpha=1.0, deltas=np.array([-1.0, 0.0, 1.0, 2.0]), theta=0.0)
        assert ll < 0  # 对数似然应为负

    @pytest.mark.skipif(not _HAS_NUMBA_IRT, reason="Numba 未安装")
    def test_numba_prob_matches_numpy(self, gpcm: GPCM) -> None:
        """Numba 版本与 NumPy 版本结果一致。"""
        thetas = np.linspace(-2, 2, 5)
        deltas = np.array([-1.0, 0.0, 1.0])
        alpha = 1.2
        numba_probs = gpcm.prob_matrix(thetas, alpha, deltas)
        np_probs = np.zeros_like(numba_probs)
        for i, t in enumerate(thetas):
            from scipy.special import softmax
            scores = alpha * (np.arange(len(deltas)) * t - deltas)
            np_probs[i] = softmax(scores)
        assert np.allclose(numba_probs, np_probs, atol=1e-6)


class TestGRM:
    """GRM 模型测试。"""

    @pytest.fixture
    def grm(self) -> GRM:
        return GRM(n_categories=5)

    def test_prob_returns_correct_shape(self, grm: GRM) -> None:
        probs = grm.prob(0.0, alpha=1.5, betas=np.array([-1.5, -0.5, 0.5, 1.5]))
        assert len(probs) == 5
        assert abs(np.sum(probs) - 1.0) < 1e-6

    def test_prob_sum_to_one(self, grm: GRM) -> None:
        for theta in [-3, -1, 0, 1, 3]:
            probs = grm.prob(theta, alpha=1.0, betas=np.array([-1.0, 0.0, 1.0]))
            assert abs(np.sum(probs) - 1.0) < 1e-6, f"theta={theta}"

    def test_eap_estimate(self, grm: GRM) -> None:
        responses = np.array([3, 2, 4, 1])
        theta, se = grm.eap_estimate(responses, alpha=1.0, betas=np.array([-1.0, 0.0, 1.0, 2.0]))
        assert isinstance(theta, float)
        assert se > 0


class TestModelSelector:
    """模型选择器测试。"""

    def test_select_3pl_for_dichotomous(self) -> None:
        assert select_model("单选题", 1.0) == "3pl"

    def test_select_gpcm_for_partial_credit(self) -> None:
        assert select_model("填空题", 4.0) == "gpcm"

    def test_select_grm_for_essay(self) -> None:
        assert select_model("论述题", 6.0) == "grm"

    def test_select_grm_for_high_score(self) -> None:
        assert select_model("自定义", 10.0) == "grm"


class TestFitIndices:
    """拟合指数测试。"""

    def test_compute_fit_indices_returns_dict(self) -> None:
        indices = compute_fit_indices(
            loglik_model=-1000.0, loglik_null=-1200.0,
            n_params=30, n_items=20, n_obs=5000,
        )
        assert "CFI" in indices
        assert "TLI" in indices
        assert "RMSEA" in indices
        assert "AIC" in indices
        assert "BIC" in indices
        assert indices["CFI"] > 0  # 模型应优于零模型
