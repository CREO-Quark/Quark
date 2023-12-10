import json
import numpy as np
import plotly.graph_objects as go


class BootstrapLinearRegression:
    """
    BootstrapLinearRegression class for performing linear regression with bootstrapping.

    Attributes:
        coefficient (numpy.ndarray): Coefficients of the linear regression model.
        bootstrap_samples (int): Number of bootstrap samples to generate.
        bootstrap_block_size (float): Block size as a percentage of the dataset length for block bootstrap.
        bootstrap_coefficients (list): List to store bootstrap sample coefficients.

    Methods:
        fit(x, y, use_bootstrap=True, method='standard'): Fit the linear regression model to the data.
        bootstrap_standard(x, y): Generate bootstrap samples using the standard method.
        bootstrap_block(x, y): Generate bootstrap samples using the block bootstrap method.
        predict(x, alpha=0.05): Make predictions with prediction intervals.
        plot(x, y, x_axis, alpha=0.05): Plot the data, fitted line, and prediction interval using Plotly.
        to_json(fmt='dict'): Serialize the model to a JSON format.
        from_json(json_str): Deserialize the model from a JSON format.

    Usage:
        model = BootstrapLinearRegression()
        model.fit(x, y, use_bootstrap=True, method='block')
        model.plot(x=x, y=y, x_axis=index)
    """

    def __init__(self, bootstrap_samples: int = 100, bootstrap_block_size: float = 0.05):
        """
        Initialize the BootstrapLinearRegression object.

        Args:
            bootstrap_samples (int): Number of bootstrap samples to generate.
            bootstrap_block_size (float): Block size as a percentage of the dataset length for block bootstrap.
        """
        self.coefficient: np.ndarray | None = None

        # parameters for bootstrap
        self.bootstrap_samples = bootstrap_samples
        self.bootstrap_block_size = bootstrap_block_size
        self.bootstrap_coefficients: list[np.ndarray] = []

    def fit(self, x: list | np.ndarray, y: list | np.ndarray, use_bootstrap=True, method='standard'):
        """
        Fit the linear regression model to the data.

        Args:
            x (list or numpy.ndarray): Input features.
            y (list or numpy.ndarray): Output values.
            use_bootstrap (bool): Whether to perform bootstrap.
            method (str): Bootstrap method ('standard' or 'block').

        Returns:
            None
        """
        self.coefficient = np.linalg.lstsq(x, y, rcond=None)[0]

        if use_bootstrap:
            if method == 'standard':
                self.bootstrap_standard(x, y)
            elif method == 'block':
                self.bootstrap_block(x, y)
            else:
                raise ValueError("Invalid bootstrap method. Use 'standard' or 'block'.")

    def bootstrap_standard(self, x, y):
        """
        Generate bootstrap samples using the standard method.

        Args:
            x (list or numpy.ndarray): Input features.
            y (list or numpy.ndarray): Output values.

        Returns:
            None
        """
        n = len(x)
        for _ in range(self.bootstrap_samples):
            indices = np.random.choice(n, n, replace=True)
            x_sampled, y_sampled = x[indices], y[indices]
            coefficient = np.linalg.lstsq(x_sampled, y_sampled, rcond=None)[0]
            self.bootstrap_coefficients.append(coefficient)

    def bootstrap_block(self, x, y):
        """
        Generate bootstrap samples using the block bootstrap method.

        Args:
            x (list or numpy.ndarray): Input features.
            y (list or numpy.ndarray): Output values.

        Returns:
            None
        """
        n = len(x)
        block_size = int(self.bootstrap_block_size * n)
        num_blocks = n // block_size

        for _ in range(self.bootstrap_samples):
            indices = []
            for _ in range(num_blocks):
                block_start = np.random.randint(0, n - block_size + 1)
                indices.extend(range(block_start, block_start + block_size))

            x_sampled, y_sampled = x[indices], y[indices]
            coefficient = np.linalg.lstsq(x_sampled, y_sampled, rcond=None)[0]
            self.bootstrap_coefficients.append(coefficient)

    def predict(self, x, alpha=0.05):
        """
        Make predictions with prediction intervals.

        Args:
            x (list or numpy.ndarray): Input features.
            alpha (float): Significance level for the prediction interval.

        Returns:
            Tuple(numpy.ndarray, numpy.ndarray): Predicted values and prediction interval.
        """
        # For single input, X might be a 1D array
        if len(x.shape) == 1:
            x = x.reshape(1, -1)

        # Compute mean predictions and intervals for all input sets
        y_pred = np.dot(x, self.coefficient)

        if not self.bootstrap_coefficients:
            return y_pred, []

        residuals = []
        for bootstrap_coefficient in self.bootstrap_coefficients:
            y_bootstrap = np.dot(x, bootstrap_coefficient)
            residual = y_bootstrap - y_pred
            residuals.append(residual)

        residuals = np.array(residuals)
        lower_bound = np.quantile(residuals, alpha / 2, axis=0)
        upper_bound = np.quantile(residuals, 1 - alpha / 2, axis=0)
        interval = np.array([lower_bound, upper_bound]).T

        return y_pred, interval

    def plot(self, x, y, x_axis, alpha=0.05, **kwargs):
        """
        Plot the data, fitted line, and prediction interval using Plotly.

        Args:
            x (list or numpy.ndarray): Input features.
            y (list or numpy.ndarray): Output values.
            x_axis (list or numpy.ndarray): Values for the (plotted) x-axis.
            alpha (float): Significance level for the prediction interval.
            **kwargs: Additional keyword arguments for customizing the plot:
                - 'data_name' (str, optional): Name for the data trace on the plot. Default is "Data".
                - 'model_name' (str, optional): Name for the fitted line trace on the plot. Default is "Fitted Line".
                - 'title' (str, optional): Title for the plot. Default is "Bootstrap Linear Regression".
                - 'x_name' (str, optional): Label for the x-axis. Default is "Index".
                - 'y_name' (str, optional): Label for the y-axis. Default is "Y".

        Returns:
            plotly.graph_objects.Figure: Plotly figure object.
        """

        y_pred, interval = self.predict(x, alpha)

        fig = go.Figure()

        # Scatter plot for data
        fig.add_trace(go.Scatter(x=x_axis, y=y, mode='markers', name=kwargs.get('data_name', "Data")))

        # Line plot for fitted line
        fig.add_trace(go.Scatter(x=x_axis, y=y_pred, mode='lines', name=kwargs.get('model_name', "Fitted Line"), line=dict(color='red')))

        # Fill the area between the prediction intervals
        if self.bootstrap_coefficients:
            fig.add_trace(
                go.Scatter(
                    name=f'{alpha:.2%} Upper Bound',
                    x=x_axis,
                    y=y_pred + interval[:, 1],
                    mode='lines',
                    line=dict(color='red', dash='dash'),
                    showlegend=False
                )
            )

            fig.add_trace(
                go.Scatter(
                    name=f'{alpha:.2%} Lower Bound',
                    x=x_axis,
                    y=y_pred + interval[:, 0],
                    line=dict(color='red', dash='dash'),
                    mode='lines',
                    fillcolor='rgba(255,0,0,0.3)',
                    fill='tonexty',
                    showlegend=False
                )
            )

        # Layout settings
        fig.update_layout(
            title=kwargs.get('title', "Bootstrap Linear Regression"),
            xaxis_title=kwargs.get('x_name', "Index"),
            yaxis_title=kwargs.get('y_name', "Y"),
            hovermode="x unified",  # Enable hover for the x-axis
        )

        return fig

    def to_json(self, fmt='dict') -> dict | str:
        """
        Serialize the model to a JSON format.

        Args:
            fmt (str): Format for serialization ('dict' or 'json').

        Returns:
            dict or str: Serialized model.
        """
        json_dict = dict(
            coefficient=self.coefficient.tolist() if self.coefficient is not None else None,
            bootstrap_samples=self.bootstrap_samples,
            bootstrap_block_size=self.bootstrap_block_size,
            bootstrap_coefficients=[_.tolist() for _ in self.bootstrap_coefficients]
        )

        if fmt == 'dict':
            return json_dict
        else:
            return json.dumps(json_dict)

    @classmethod
    def from_json(cls, json_str: str | bytes | dict):
        """
        Deserialize the model from a JSON format.

        Args:
            json_str (str, bytes, or dict): Serialized model.

        Returns:
            BootstrapLinearRegression: Deserialized model.
        """
        if isinstance(json_str, (str, bytes)):
            json_dict = json.loads(json_str)
        elif isinstance(json_str, dict):
            json_dict = json_str
        else:
            raise TypeError(f'{cls.__name__} can not load from json {json_str}')

        self = cls(
            bootstrap_samples=json_dict['bootstrap_samples'],
            bootstrap_block_size=json_dict['bootstrap_block_size']
        )

        self.coefficient = np.array(json_dict['coefficient'])
        self.bootstrap_coefficients.extend([np.array(_) for _ in json_dict['bootstrap_coefficients']])

        return self


def test():
    """
    Test the BootstrapLinearRegression class with synthetic data.

    Returns:
        None
    """
    np.random.seed(42)
    n = 100
    index = np.arange(n)
    x = np.column_stack((np.ones(n), index, 3 * index + 20 + 0.04 * (index - 50) ** 2))
    y = 5 * index + 5 * (index - 50) ** 2 + np.random.normal(scale=500, size=n) + np.random.normal(scale=100, size=n) * (index - 50)

    # Example usage:
    model = BootstrapLinearRegression(bootstrap_samples=50)
    model.fit(x, y, use_bootstrap=True, method='block')

    json_dump = model.to_json()
    model = BootstrapLinearRegression.from_json(json_dump)

    # Use the index as the x_axis
    fig = model.plot(x=x, y=y, x_axis=index)
    fig.show()


if __name__ == '__main__':
    test()
