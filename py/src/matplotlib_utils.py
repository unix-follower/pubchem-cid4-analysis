import matplotlib.pyplot as plt


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
