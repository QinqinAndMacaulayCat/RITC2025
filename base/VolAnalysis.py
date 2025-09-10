"""
Analyze volatility of price.

Author: DQ
Date: 2025-01-03
"""

import numpy as np
import logging
from typing import Any
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from arch import arch_model
from RITC.base.utils import ModelNotFitException

logger = logging.getLogger(__name__)

class PriceTrendModel:
    p_range=range(1, 5)
    d_range=range(0, 1)
    q_range=range(1, 5)

    def __init__(self, price_data: np.ndarray) -> None:
        """
        Initialize the PriceTrendModel with price data.
        Args:
            price_data (np.ndarray): Array of price data.
        """
        self.price_data: np.ndarray = price_data
        self.stationary_data: np.ndarray | None = None
        self.differencing_order: int = self.make_stationary()  # To store the order of differencing used
        self.best_model: ARIMA | None = None
        self.best_aic: float = np.inf
        self.best_bic: float = np.inf
        self.best_order: tuple | None = None
        self.garch_model: Any = None
        self.volatility_forecast: float | None = None  # To store the forecasted volatility
        self.volatility_percentage_rank: float | None = None  # To store the percentage rank of volatility

    def _split_data(self, train_ratio: float = 0.8) -> tuple:
        """
        Split the data into training and test sets.
        Args:
            train_ratio (float): Ratio of data to use for training.
        Returns:
            tuple: (train, test) arrays.
        """
        train_size = int(len(self.stationary_data) * train_ratio)
        train, test = self.stationary_data[:train_size], self.stationary_data[train_size:]
        return train, test

    def check_stationarity(self, series: np.ndarray) -> bool:
        """
        Perform the Augmented Dickey-Fuller test to check for stationarity.
        Args:
            series (np.ndarray): Time series data.
        Returns:
            bool: True if stationary, False otherwise.
        """
        adf_result = adfuller(series)
        p_value = adf_result[1]
        return p_value < 0.05

    def make_stationary(self) -> int:
        """
        Ensure the series is stationary by differencing if necessary.
        Returns:
            int: Number of differences applied to achieve stationarity.
        """
        data = self.price_data
        d = 0
        if_stationary = self.check_stationarity(data)
        while d < 2:
            if not if_stationary:
                logger.info(f"Differencing series, attempt {d+1}")
                data = data[1:] - data[:-1]
                if_stationary = self.check_stationarity(data)
                d += 1
            else:
                break
        if if_stationary:
            logger.info(f"Series differenced {d} time(s) to achieve stationarity.")
            self.stationary_data = data
            self.differencing_order = d
        else:
            logger.warning("Series is not stationary after differencing.")
            self.stationary_data = None
            self.differencing_order = 0
        return d
        
    
    def __evaluate_model(self, order: tuple, train: np.ndarray) -> tuple:
        """
        Fit ARIMA model and calculate AIC/BIC.
        Args:
            order (tuple): ARIMA order (p, d, q).
            train (np.ndarray): Training data.
        Returns:
            tuple: (AIC, BIC, model_fit)
        """
        try:
            model = ARIMA(train, order=order)
            model_fit = model.fit()
            return model_fit.aic, model_fit.bic, model_fit
        except Exception as e:
            logger.error(f"Error fitting model for order {order}: {e}")
            return np.inf, np.inf, None
    
    def update_data(self, price_data: np.ndarray) -> None:
        """
        Update the price data for the model.
        Args:
            price_data (np.ndarray): New price data.
        """
        self.price_data = price_data
        self.make_stationary()

    def fit_arima(self) -> None:
        """
        Fit an ARIMA model with the specified order.
        Raises:
            ModelNotFitException: If no ARIMA order has been selected.
        """
        if self.best_order is None:
            raise ModelNotFitException("No ARIMA model has been selected yet.")
        logger.info(f"Fitting ARIMA model with order {self.best_order}")
        model = ARIMA(self.stationary_data, order=self.best_order)
        self.best_model = model.fit()


    def choose_best_arima(self) -> None:
        """
        Use AIC/BIC to select the best ARIMA model.
        Raises:
            ModelNotFitException: If data is not stationary.
        """
        if self.stationary_data is None:
            raise ModelNotFitException("Data is not stationary. Cannot fit ARIMA model.")
        train, _ = self._split_data()
        for p in self.p_range:
            for d in self.d_range:
                for q in self.q_range:
                    aic_value, bic_value, model_fit = self.__evaluate_model((p, d, q), train)
                    if aic_value < self.best_aic:
                        self.best_aic = aic_value
                        self.best_bic = bic_value
                        self.best_order = (p, d, q)
                        self.best_model = model_fit
        logger.info(f"Best ARIMA model: ARIMA{self.best_order} with AIC={self.best_aic} and BIC={self.best_bic}")


    @staticmethod
    def rolling_std(arr: np.ndarray, window_size: int) -> np.ndarray:
        """
        Calculate rolling standard deviation for a given array and window size.
        Args:
            arr (np.ndarray): Input array.
            window_size (int): Size of the rolling window.
        Returns:
            np.ndarray: Array of rolling standard deviations.
        """
        def manual_std(arr: np.ndarray) -> float:
            n = len(arr)
            mean = np.sum(arr) / n
            variance = np.sum((arr - mean) ** 2) / n
            std = np.sqrt(variance)
            return std
        n = len(arr)
        stds = []
        for i in range(n - window_size + 1):
            window = arr[i:min(i + window_size, n)]
            stds.append(manual_std(window))
        return np.array(stds)


    def fit_garch(self) -> None:
        """
        Fit a GARCH model on the residuals of the ARIMA model to model volatility.
        Raises:
            ModelNotFitException: If no ARIMA model has been selected.
        """
        if self.best_model is None:
            raise ModelNotFitException("No ARIMA model has been selected yet.")
        residuals = self.best_model.resid
        historical_volatility = self.rolling_std(residuals, window_size=10)
        garch = arch_model(residuals, vol='Garch', p=1, q=1)
        self.garch_model = garch.fit(disp="off")
        logger.info(f"GARCH Model Summary:\n{self.garch_model.summary()}")
        forecast_res = self.garch_model.forecast(horizon=1)
        logger.info(f"Forecasted Volatility: {forecast_res.variance}")
        self.volatility_forecast = forecast_res.variance.values[-1, 0] ** 0.5
        self.volatility_percentage_rank = sum(self.volatility_forecast > historical_volatility) / len(historical_volatility)
        logger.info(f"Volatility Forecast Percentage Rank: {self.volatility_percentage_rank}")
        logger.info(f"historical_volatility: {historical_volatility}")


    def forecast(self, steps: int = 10) -> np.ndarray | None:
        """
        Forecast future values using the best ARIMA model.
        Args:
            steps (int): Number of steps to forecast.
        Returns:
            np.ndarray | None: Forecasted values or None if no model is fit.
        """
        if self.best_model is None:
            logger.warning("No ARIMA model has been selected yet.")
            return None
        forecast_values = self.best_model.forecast(steps=steps)
        logger.info(f"Forecasted Values: {forecast_values}")
        return forecast_values
