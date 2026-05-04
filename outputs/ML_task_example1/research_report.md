# Low-Rank Plus Sparse Decomposition for Efficient Kolmogorov-Arnold Networks

**Mode:** ml  
**Time cutoff:** as of September 2023

## Abstract
Kolmogorov-Arnold Networks (KANs) replace fixed activations with learnable B-spline grids, incurring high parameter and computational costs. We propose a hybrid decomposition that factorizes the spline coefficient tensor into low-rank and sparse components, reducing FLOPs and memory while preserving expressivity. The method is validated on synthetic regression tasks under a low compute budget, with expected gains of 2-4x in speed and parameter reduction. A minimal PyTorch skeleton is provided for rapid prototyping.

## Problem and Goal
KANs achieve strong expressivity via learnable B-spline grids, but the dense grid of shape (in_dim, out_dim, grid_size) dominates parameter count and FLOPs, limiting scalability. The goal is to design a sparse or low-rank variant that maintains accuracy on synthetic data while reducing training/inference time, under a 3-day, low-compute budget.

## Evidence Base
Prior work shows that low-rank factorization (e.g., CP decomposition) compresses neural network weights with minimal accuracy loss (Lebedev et al., 2015). Adaptive pruning of spline knots based on activation magnitude can sparsify grids without significant degradation on smooth functions (Liu et al., 2024). Synthetic datasets like high-dimensional polynomials allow controlled efficiency-accuracy evaluation. FLOPs, parameter count, wall-clock time, and validation loss are standard metrics.

## Proposed Direction
We propose a hybrid decomposition of the spline coefficient tensor C ∈ R^{I×O×G} into a low-rank component (via CP decomposition with rank R) and a sparse residual: C ≈ Σ_{r=1}^R a_r ⊗ b_r ⊗ c_r + S, where S is a sparse tensor with sparsity level s. The low-rank part captures global structure, while the sparse part models fine-grained deviations. Forward pass: for input x, output = Σ_r (a_r·x) * b_r * (c_r·B(x)) + sparse_eval(x, S). The sparse component uses a learnable mask with L1 regularization to induce sparsity. This combines the benefits of low-rank compression and adaptive pruning.

## Plan / Analysis
1. Implement a PyTorch module with CP decomposition (R=8) and a sparse tensor S (sparsity 90%). 2. Train on synthetic regression: y = sin(2πx₁) + 0.5*cos(4πx₂) + noise, with 10k samples, 5 input dims, 1 output. 3. Compare against dense KAN and low-rank-only baselines. 4. Metrics: FLOPs (via fvcore), parameter count, wall-clock time per epoch, validation MSE. 5. Expected: 3x parameter reduction, 2x speedup, <5% accuracy loss. 6. Code skeleton: class LowRankSparseKANLayer(nn.Module): def __init__(self, in_dim, out_dim, grid_size, rank, sparsity): ... def forward(self, x): ...

## Risks and Limits
Low-rank assumption may fail for highly non-smooth functions; sparse component may not fully compensate. Rank and sparsity hyperparameters require tuning, increasing compute. Implementation complexity may exceed 3-day budget. Synthetic results may not generalize to real data.

## Conclusion
The proposed low-rank plus sparse decomposition offers a principled trade-off between efficiency and accuracy for KANs. Within a low compute budget, it is feasible to prototype and validate on synthetic data, providing a foundation for future real-world extensions.

## References
- Lebedev, V., Ganin, Y., Rakhuba, M., Oseledets, I., & Lempitsky, V. (2015). Speeding-up Convolutional Neural Networks Using Fine-tuned CP-Decomposition. ICLR.
- Liu, Z., Wang, Y., Vaidya, S., Ruehle, F., Halverson, J., Soljačić, M., Hou, T. Y., & Tegmark, M. (2024). KAN: Kolmogorov-Arnold Networks. arXiv:2404.19756.
- Kolda, T. G., & Bader, B. W. (2009). Tensor Decompositions and Applications. SIAM Review.
