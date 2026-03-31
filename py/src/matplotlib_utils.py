import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


def plot_2d_vector(x_component: float, y_component: float):
    # Define the starting point of the vector
    x_origin = 0
    y_origin = 0

    plt.figure(figsize=(6, 6))
    plt.quiver(x_origin, y_origin, x_component, y_component, angles="xy", scale_units="xy", scale=1, color="red")

    plt.xlim(-10, 10)
    plt.ylim(-10, 10)

    plt.xlabel("x-axis")
    plt.ylabel("y-axis")
    plt.title("2D Vector")
    plt.grid(True)
    plt.show()


def plot_pic50_transform(
    ic50_values_um: np.ndarray,
    pic50_values: np.ndarray,
    out_file_path: str,
):
    if ic50_values_um.size == 0 or pic50_values.size == 0:
        raise ValueError("pIC50 plot requires at least one positive IC50 value")

    min_ic50 = float(np.min(ic50_values_um))
    max_ic50 = float(np.max(ic50_values_um))

    if np.isclose(min_ic50, max_ic50):
        min_ic50 = max(min_ic50 / 10.0, 1e-6)
        max_ic50 = max_ic50 * 10.0

    curve_x = np.geomspace(min_ic50, max_ic50, 200)
    curve_y = -np.log10(curve_x)

    plt.figure(figsize=(10, 6))
    plt.plot(curve_x, curve_y, color="navy", linewidth=2, label=r"$y = -\log_{10}(x)$")
    plt.scatter(
        ic50_values_um,
        pic50_values,
        color="darkorange",
        edgecolors="black",
        linewidths=0.5,
        s=55,
        alpha=0.85,
        label="Observed IC50 rows",
    )
    plt.xscale("log")
    plt.xlabel("IC50 (uM)")
    plt.ylabel("pIC50")
    plt.title("pIC50 Transform Across Observed IC50 Range")
    plt.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_file_path, dpi=200)
    plt.close()


def plot_hill_reference_curves(
    representative_k_values: np.ndarray,
    representative_labels: list[str],
    hill_coefficient: float,
    out_file_path: str,
):
    if representative_k_values.size == 0:
        raise ValueError("Hill reference-curve plot requires at least one inferred K value")

    min_k = float(np.min(representative_k_values))
    max_k = float(np.max(representative_k_values))
    concentration_grid = np.geomspace(max(min_k / 100.0, 1e-6), max_k * 100.0, 400)

    plt.figure(figsize=(10, 6))

    for k_value, label in zip(representative_k_values, representative_labels, strict=True):
        response_curve = (concentration_grid**hill_coefficient) / (
            (k_value**hill_coefficient) + (concentration_grid**hill_coefficient)
        )
        plt.plot(concentration_grid, response_curve, linewidth=2, label=label)
        plt.axvline(k_value, linestyle="--", linewidth=1, alpha=0.7)

    plt.xscale("log")
    plt.ylim(-0.02, 1.02)
    plt.xlabel("Concentration c (same units as Activity_Value)")
    plt.ylabel("Normalized response f(c)")
    plt.title(f"Reference Hill Curves Inferred from Activity_Value (n = {hill_coefficient:g})")
    plt.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_file_path, dpi=200)
    plt.close()


def plot_activity_value_statistics(
    activity_values: np.ndarray,
    include_qq_panel: bool,
    out_file_path: str,
):
    if activity_values.size == 0:
        raise ValueError("Activity_Value statistics plot requires at least one retained row")

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    histogram_axis = axes[0]
    qq_axis = axes[1]

    histogram_axis.hist(activity_values, bins="auto", color="steelblue", edgecolor="black", alpha=0.85)
    histogram_axis.set_xscale("log")
    histogram_axis.set_xlabel("Activity_Value")
    histogram_axis.set_ylabel("Frequency")
    histogram_axis.set_title("Positive Numeric Activity_Value Histogram")
    histogram_axis.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.4)

    values_have_spread = not np.isclose(float(activity_values.min()), float(activity_values.max()))
    if include_qq_panel and values_have_spread:
        fitted_mean = float(np.mean(activity_values))
        fitted_std = float(np.std(activity_values, ddof=1)) if activity_values.size > 1 else 0.0
        if fitted_std > 0:
            stats.probplot(activity_values, dist="norm", sparams=(fitted_mean, fitted_std), plot=qq_axis)
            qq_axis.set_title("Normal Q-Q Plot")
            qq_axis.grid(True, linestyle="--", linewidth=0.6, alpha=0.4)
        else:
            qq_axis.text(0.5, 0.5, "Q-Q plot unavailable\nzero variance sample", ha="center", va="center")
            qq_axis.set_axis_off()
    else:
        qq_axis.text(0.5, 0.5, "Q-Q plot unavailable\ninsufficient or degenerate sample", ha="center", va="center")
        qq_axis.set_axis_off()

    figure.tight_layout()
    figure.savefig(out_file_path, dpi=200)
    plt.close(figure)


def plot_gradient_descent_loss_curve(
    epochs: np.ndarray,
    mse_values: np.ndarray,
    out_file_path: str,
):
    if epochs.size == 0 or mse_values.size == 0:
        raise ValueError("Gradient-descent loss plot requires at least one epoch")

    plt.figure(figsize=(10, 6))
    plt.plot(epochs, mse_values, color="teal", linewidth=2)
    plt.xlabel("Epoch")
    plt.ylabel("MSE")
    plt.title("Manual Gradient Descent MSE Trace")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_file_path, dpi=200)
    plt.close()


def plot_atom_element_entropy(
    elements: list[str],
    proportions: np.ndarray,
    entropy_value: float,
    out_file_path: str,
):
    if len(elements) == 0 or proportions.size == 0:
        raise ValueError("Atom element entropy plot requires at least one element")

    plt.figure(figsize=(8, 5))
    bars = plt.bar(elements, proportions, color=["#4c78a8", "#f58518", "#54a24b", "#e45756"][: len(elements)])
    plt.ylim(0.0, max(1.0, float(np.max(proportions)) * 1.15))
    plt.xlabel("Element")
    plt.ylabel("Proportion")
    plt.title(f"Atom Element Proportions (H = {entropy_value:.4f})")
    plt.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)

    for bar, proportion in zip(bars, proportions, strict=True):
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            float(bar.get_height()) + 0.015,
            f"{float(proportion):.3f}",
            ha="center",
            va="bottom",
        )

    plt.tight_layout()
    plt.savefig(out_file_path, dpi=200)
    plt.close()


def plot_gradient_descent_fit(
    mass_values: np.ndarray,
    atomic_number_values: np.ndarray,
    learned_weight: float,
    out_file_path: str,
):
    if mass_values.size == 0 or atomic_number_values.size == 0:
        raise ValueError("Gradient-descent fit plot requires at least one atom feature row")

    max_mass = float(np.max(mass_values))
    line_x = np.linspace(0.0, max_mass * 1.05, 200)
    line_y = learned_weight * line_x

    plt.figure(figsize=(10, 6))
    plt.scatter(
        mass_values,
        atomic_number_values,
        color="slateblue",
        edgecolors="black",
        linewidths=0.5,
        s=55,
        alpha=0.85,
        label="Atom feature rows",
    )
    plt.plot(line_x, line_y, color="crimson", linewidth=2, label=rf"$\hat{{y}} = {learned_weight:.4f}x$")
    plt.xlabel("Atom mass")
    plt.ylabel("Atomic number")
    plt.title("Manual Gradient Descent Fit: Mass to Atomic Number")
    plt.grid(True, linestyle="--", linewidth=0.6, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_file_path, dpi=200)
    plt.close()
