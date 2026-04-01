"""Time series tools — forecasting, decomposition, stationarity tests, ACF/PACF."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_timeseries_tools(mcp: FastMCP) -> None:
    """Register time series analysis tools with the MCP server."""

    @mcp.tool()
    async def forecast_timeseries(
        ctx: Context,
        code: str,
        horizon: int = 12,
        method: str = "auto.arima",
        filename: str = "forecast.png",
    ) -> str:
        """Fit a time series model and produce a forecast with plot.

        The code must create a ts object named `y`.

        Args:
            code: R code that creates a ts object named `y`.
                  Example: 'y <- ts(AirPassengers, frequency=12)'
            horizon: Number of periods to forecast (default 12).
            method: Forecasting method — "auto.arima", "ets", "tbats",
                    "hw" (Holt-Winters), "stlf", "naive", "snaive".
            filename: Output plot filename (saved in ~/r-mcp-workspace/).

        Returns:
            JSON with model summary, forecast values, accuracy metrics, and plot path.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            method_map = {
                "auto.arima": f"forecast::auto.arima(y)",
                "ets": f"forecast::ets(y)",
                "tbats": f"forecast::tbats(y)",
                "hw": f"HoltWinters(y)",
                "stlf": f"forecast::stlf(y, h = {horizon})",
                "naive": f"forecast::naive(y, h = {horizon})",
                "snaive": f"forecast::snaive(y, h = {horizon})",
            }
            fit_cmd = method_map.get(method, method_map["auto.arima"])
            needs_forecast = method not in ("stlf", "naive", "snaive")

            wrapped = (
                'library(forecast)\nlibrary(jsonlite)\n'
                f'{code}\n'
                f'model <- {fit_cmd}\n'
            )
            if needs_forecast:
                wrapped += f'fc <- forecast(model, h = {horizon})\n'
            else:
                wrapped += 'fc <- model\n'

            wrapped += (
                f'png("{out_path}", width = 1024, height = 600, res = 150)\n'
                'plot(fc, main = paste("Forecast —", fc$method))\n'
                'dev.off()\n'
                'acc <- accuracy(fc)\n'
                'cat(toJSON(list(\n'
                '    method = fc$method,\n'
                '    forecast = data.frame(\n'
                '        point = as.numeric(fc$mean),\n'
                '        lo80 = as.numeric(fc$lower[,1]),\n'
                '        hi80 = as.numeric(fc$upper[,1]),\n'
                '        lo95 = as.numeric(fc$lower[,2]),\n'
                '        hi95 = as.numeric(fc$upper[,2])\n'
                '    ),\n'
                '    accuracy = as.list(acc[1,]),\n'
                '    model_summary = capture.output(summary(model)),\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=60)
            if rc != 0:
                return json.dumps({"error": stderr or "Forecast failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def decompose_timeseries(
        ctx: Context,
        code: str,
        method: str = "stl",
        filename: str = "decomposition.png",
    ) -> str:
        """Decompose a time series into trend, seasonal, and remainder.

        The code must create a ts object named `y`.

        Args:
            code: R code that creates a ts object named `y`.
            method: Decomposition method — "stl" (default), "classical",
                    "seats" (requires seasonal package).
            filename: Output plot filename.

        Returns:
            JSON with seasonal strength, trend strength, and plot path.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            if method == "stl":
                decomp_cmd = 'dec <- stl(y, s.window = "periodic")'
                comp_cmd = 'comps <- dec$time.series'
            else:
                decomp_cmd = 'dec <- decompose(y)'
                comp_cmd = ('comps <- cbind(seasonal = dec$seasonal,\n'
                            '    trend = dec$trend, remainder = dec$random)')

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'{decomp_cmd}\n'
                f'{comp_cmd}\n'
                f'png("{out_path}", width = 1024, height = 768, res = 150)\n'
                'plot(dec, main = "Time Series Decomposition")\n'
                'dev.off()\n'
                '# Strength metrics\n'
                'remainder <- comps[, "remainder"]\n'
                'trend <- comps[, "trend"]\n'
                'seasonal <- comps[, "seasonal"]\n'
                'var_r <- var(remainder, na.rm = TRUE)\n'
                'trend_str <- max(0, 1 - var_r / var(trend + remainder, na.rm = TRUE))\n'
                'seas_str <- max(0, 1 - var_r / var(seasonal + remainder, na.rm = TRUE))\n'
                'cat(toJSON(list(\n'
                '    method = "' + method + '",\n'
                '    trend_strength = round(trend_str, 4),\n'
                '    seasonal_strength = round(seas_str, 4),\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Decomposition failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def stationarity_test(
        ctx: Context,
        code: str,
        test: str = "adf",
    ) -> str:
        """Test a time series for stationarity (unit root).

        The code must create a numeric vector or ts object named `y`.

        Args:
            code: R code that creates a vector/ts named `y`.
            test: Test type — "adf" (Augmented Dickey-Fuller, default),
                  "kpss", "pp" (Phillips-Perron).

        Returns:
            JSON with test statistic, p-value, and stationarity conclusion.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            if test == "adf":
                test_cmd = (
                    'library(urca)\n'
                    'result <- ur.df(y, type = "drift", selectlags = "AIC")\n'
                    's <- summary(result)\n'
                    'stat <- result@teststat[1]\n'
                    'crit <- result@cval[1,]\n'
                    'stationary <- stat < crit["5pct"]\n'
                    'out <- list(test = "ADF", statistic = stat,\n'
                    '    critical_values = as.list(crit),\n'
                    '    stationary_5pct = stationary,\n'
                    '    summary = capture.output(s))\n'
                )
            elif test == "kpss":
                test_cmd = (
                    'library(urca)\n'
                    'result <- ur.kpss(y, type = "mu")\n'
                    's <- summary(result)\n'
                    'stat <- result@teststat[1]\n'
                    'crit <- result@cval[1,]\n'
                    'stationary <- stat < crit["5pct"]\n'
                    'out <- list(test = "KPSS", statistic = stat,\n'
                    '    critical_values = as.list(crit),\n'
                    '    stationary_5pct = stationary,\n'
                    '    note = "KPSS: H0 = stationary",\n'
                    '    summary = capture.output(s))\n'
                )
            else:
                test_cmd = (
                    'result <- PP.test(y)\n'
                    'out <- list(test = "Phillips-Perron",\n'
                    '    statistic = result$statistic,\n'
                    '    p_value = result$p.value,\n'
                    '    stationary_5pct = result$p.value < 0.05,\n'
                    '    summary = capture.output(result))\n'
                )

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'{test_cmd}'
                'cat(toJSON(out, auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Test failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def acf_pacf_plot(
        ctx: Context,
        code: str,
        max_lag: int = 40,
        filename: str = "acf_pacf.png",
    ) -> str:
        """Plot the ACF and PACF of a time series side by side.

        The code must create a numeric vector or ts object named `y`.

        Args:
            code: R code that creates a vector/ts named `y`.
            max_lag: Maximum number of lags to display (default 40).
            filename: Output plot filename.

        Returns:
            JSON with plot path and significant lag counts.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'png("{out_path}", width = 1200, height = 500, res = 150)\n'
                'par(mfrow = c(1, 2))\n'
                f'a <- acf(y, lag.max = {max_lag}, main = "ACF", plot = TRUE)\n'
                f'p <- pacf(y, lag.max = {max_lag}, main = "PACF", plot = TRUE)\n'
                'dev.off()\n'
                'ci <- qnorm(0.975) / sqrt(length(y))\n'
                'sig_acf <- sum(abs(a$acf[-1]) > ci)\n'
                'sig_pacf <- sum(abs(p$acf) > ci)\n'
                'cat(toJSON(list(\n'
                f'    plot = "{out_path}",\n'
                '    n_obs = length(y),\n'
                '    significant_acf_lags = sig_acf,\n'
                '    significant_pacf_lags = sig_pacf,\n'
                '    confidence_bound = round(ci, 4)\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "ACF/PACF failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
