import matplotlib.pyplot as plt
import numpy as np


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
