"""Forecast personal footprint series with uncertainty and an explicit fallback."""

import math
import statistics


class FootprintForecaster:
    def __init__(self):
        try:
            from statsmodels.tsa.arima.model import ARIMA
            self.arima_class = ARIMA
        except ImportError:
            self.arima_class = None

    @property
    def capability(self):
        return {"arima_available": self.arima_class is not None,
                "minimum_arima_observations": 8}

    def forecast(self, values, steps=7):
        values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
        steps = max(1, min(int(steps), 31))
        if len(values) < 3:
            return {"status": "insufficient-data", "minimum_entries": 3, "observations": len(values)}
        if self.arima_class is not None and len(values) >= 8 and len(set(values)) > 2:
            try:
                fitted = self.arima_class(values, order=(1, 1, 1)).fit()
                prediction = fitted.get_forecast(steps=steps)
                means = prediction.predicted_mean.tolist()
                intervals = prediction.conf_int(alpha=0.05)
                return {
                    "status": "ready", "method": "ARIMA(1,1,1)", "observations": len(values),
                    "points": [
                        {"step": index + 1, "point_kg": round(max(0, means[index]), 3),
                         "low_kg": round(max(0, float(intervals[index][0])), 3),
                         "high_kg": round(max(0, float(intervals[index][1])), 3)}
                        for index in range(steps)
                    ],
                    "interpretation": "95% model interval; factor uncertainty is reported separately.",
                }
            except Exception:
                pass
        window = values[-7:]
        point = statistics.mean(window)
        spread = statistics.stdev(window) if len(window) > 1 else 0
        return {
            "status": "ready", "method": "rolling-mean-fallback", "observations": len(values),
            "points": [
                {"step": index + 1, "point_kg": round(point, 3),
                 "low_kg": round(max(0, point - 1.96 * spread), 3),
                 "high_kg": round(point + 1.96 * spread, 3)}
                for index in range(steps)
            ],
            "interpretation": "Exploratory 95% empirical band from up to seven recent observations.",
        }
