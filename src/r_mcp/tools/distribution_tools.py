"""Probability distribution tools — d/p/q/r families, sampling, scaling."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_distribution_tools(mcp: FastMCP) -> None:
    """Register probability distribution tools with the MCP server."""

    @mcp.tool()
    async def distribution_calculator(
        ctx: Context,
        distribution: str,
        function_type: str,
        x: str,
        param1: float = 0.0,
        param2: float = 1.0,
        lower_tail: bool = True,
    ) -> str:
        """Compute probability distribution values (density, CDF, quantile, random).

        Covers all base R distributions: normal, binomial, uniform, exponential,
        poisson, t, F, chi-squared, beta, gamma, geometric, negative binomial,
        hypergeometric, Weibull, log-normal, Cauchy.

        Args:
            distribution: Distribution name — "norm", "binom", "unif", "exp",
                "pois", "t", "f", "chisq", "beta", "gamma", "geom", "nbinom",
                "hyper", "weibull", "lnorm", "cauchy".
            function_type: "d" (density/PMF), "p" (CDF), "q" (quantile),
                "r" (random).
            x: Values to evaluate — e.g. "0.5", "c(1,2,3)", "seq(0,1,0.1)",
                or for "r" the number of samples as a string like "100".
            param1: First parameter (mean for norm, size for binom, min for unif,
                rate for exp, lambda for pois, df for t/chisq, df1 for f,
                shape1 for beta, shape for gamma/weibull, prob for geom).
            param2: Second parameter (sd for norm, prob for binom, max for unif,
                df2 for f, shape2 for beta, rate for gamma, scale for weibull).
            lower_tail: For "p" and "q" functions — TRUE for P(X<=x),
                FALSE for P(X>x). Default TRUE.

        Returns:
            JSON with computed values and distribution info.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            param_map = {
                "norm": f"mean={param1}, sd={param2}",
                "binom": f"size={int(param1)}, prob={param2}",
                "unif": f"min={param1}, max={param2}",
                "exp": f"rate={param1}",
                "pois": f"lambda={param1}",
                "t": f"df={param1}",
                "f": f"df1={param1}, df2={param2}",
                "chisq": f"df={param1}",
                "beta": f"shape1={param1}, shape2={param2}",
                "gamma": f"shape={param1}, rate={param2}",
                "geom": f"prob={param1}",
                "nbinom": f"size={int(param1)}, prob={param2}",
                "weibull": f"shape={param1}, scale={param2}",
                "lnorm": f"meanlog={param1}, sdlog={param2}",
                "cauchy": f"location={param1}, scale={param2}",
            }
            if distribution not in param_map:
                return json.dumps({"error": f"Unknown distribution: {distribution}"})

            params = param_map[distribution]
            fn = f"{function_type}{distribution}"
            lt = "TRUE" if lower_tail else "FALSE"

            if function_type in ("p", "q"):
                call = f'{fn}({x}, {params}, lower.tail={lt})'
            else:
                call = f'{fn}({x}, {params})'

            code = (
                'library(jsonlite)\n'
                f'result <- {call}\n'
                'cat(toJSON(list(\n'
                f'    distribution = "{distribution}",\n'
                f'    function_type = "{function_type}",\n'
                '    values = result\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Distribution calc failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def distribution_plot(
        ctx: Context,
        distribution: str,
        param1: float = 0.0,
        param2: float = 1.0,
        n_samples: int = 1000,
        filename: str = "distribution.png",
    ) -> str:
        """Plot a probability distribution: histogram of random samples with
        theoretical density overlay.

        Args:
            distribution: Distribution name — "norm", "binom", "unif", "exp",
                "pois", "t", "chisq", "beta", "gamma", "weibull", "lnorm".
            param1: First parameter (see distribution_calculator).
            param2: Second parameter (see distribution_calculator).
            n_samples: Number of random samples to draw (default 1000).
            filename: Output PNG filename.

        Returns:
            JSON with plot path and summary statistics of sample.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            param_map = {
                "norm": (f"mean={param1}, sd={param2}", True),
                "binom": (f"size={int(param1)}, prob={param2}", False),
                "unif": (f"min={param1}, max={param2}", True),
                "exp": (f"rate={param1}", True),
                "pois": (f"lambda={param1}", False),
                "t": (f"df={param1}", True),
                "chisq": (f"df={param1}", True),
                "beta": (f"shape1={param1}, shape2={param2}", True),
                "gamma": (f"shape={param1}, rate={param2}", True),
                "weibull": (f"shape={param1}, scale={param2}", True),
                "lnorm": (f"meanlog={param1}, sdlog={param2}", True),
            }
            if distribution not in param_map:
                return json.dumps({"error": f"Unknown distribution: {distribution}"})

            params, continuous = param_map[distribution]

            code = (
                'library(jsonlite)\n'
                f'x <- r{distribution}({n_samples}, {params})\n'
                f'png("{out_path}", width = 900, height = 600, res = 150)\n'
            )
            if continuous:
                code += (
                    'hist(x, probability = TRUE, col = gray(0.9),\n'
                    f'    main = paste0("{distribution}(", "{params}", ")"),\n'
                    '    xlab = "x", border = "white")\n'
                    f'curve(d{distribution}(x, {params}), add = TRUE,\n'
                    '    col = "#E63946", lwd = 2)\n'
                )
            else:
                code += (
                    'hist(x, probability = TRUE, col = gray(0.9),\n'
                    f'    main = paste0("{distribution}(", "{params}", ")"),\n'
                    '    xlab = "x", border = "white")\n'
                    f'xvals <- min(x):max(x)\n'
                    f'points(xvals, d{distribution}(xvals, {params}),\n'
                    '    type = "h", col = "#E63946", lwd = 2)\n'
                )
            code += (
                'dev.off()\n'
                'cat(toJSON(list(\n'
                f'    distribution = "{distribution}",\n'
                '    n = length(x),\n'
                '    mean = mean(x), sd = sd(x),\n'
                '    min = min(x), max = max(x),\n'
                '    median = median(x),\n'
                '    quantiles = as.list(quantile(x)),\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Plot failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def random_sample(
        ctx: Context,
        code: str,
        n: int = 100,
        replace: bool = True,
    ) -> str:
        """Sample from a population with or without replacement (like dice,
        cards, lottery). The code must create a vector named `population`.

        Args:
            code: R code that creates a vector named `population`.
                  Examples:
                  - 'population <- 1:6'  (die)
                  - 'population <- c("H","T")'  (coin)
                  - 'population <- 1:54'  (lottery)
            n: Number of samples to draw (default 100).
            replace: Sample with replacement (default TRUE).

        Returns:
            JSON with the sample, frequency table, and summary.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            rep = "TRUE" if replace else "FALSE"
            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f's <- sample(population, {n}, replace = {rep})\n'
                'tab <- table(s)\n'
                'cat(toJSON(list(\n'
                f'    n = {n}, replace = {rep},\n'
                '    sample = s,\n'
                '    frequencies = as.list(tab),\n'
                '    proportions = as.list(prop.table(tab)),\n'
                '    unique_values = length(unique(s))\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Sample failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def qq_plot(
        ctx: Context,
        code: str,
        distribution: str = "norm",
        filename: str = "qqplot.png",
    ) -> str:
        """Create a Q-Q (quantile-quantile) plot to assess distributional fit.

        The code must create a numeric vector named `y`.

        Args:
            code: R code that creates a numeric vector named `y`.
            distribution: Reference distribution — "norm" (default), "exp",
                "unif", "t", "chisq".
            filename: Output PNG filename.

        Returns:
            JSON with plot path and Shapiro-Wilk p-value (for normality).
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            if distribution == "norm":
                qq_cmd = 'qqnorm(y, main = "Normal Q-Q Plot")\nqqline(y, col = "#E63946", lwd = 2)\n'
            else:
                qq_cmd = f'qqplot(q{distribution}(ppoints(length(y))), y, main = "{distribution} Q-Q Plot")\nqqline(y, distribution = function(p) q{distribution}(p), col = "#E63946", lwd = 2)\n'

            code_r = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'png("{out_path}", width = 800, height = 600, res = 150)\n'
                f'{qq_cmd}'
                'dev.off()\n'
                'sw <- tryCatch(shapiro.test(y), error = function(e) NULL)\n'
                'cat(toJSON(list(\n'
                f'    plot = "{out_path}",\n'
                f'    distribution = "{distribution}",\n'
                '    n = length(y),\n'
                '    shapiro_p = if (!is.null(sw)) sw$p.value else NA,\n'
                '    skewness = (mean(y) - median(y)) / sd(y)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code_r, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "QQ plot failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def simulate_clt(
        ctx: Context,
        distribution: str = "norm",
        param1: float = 0.0,
        param2: float = 1.0,
        sample_sizes: str = "1,5,15,50",
        n_simulations: int = 1000,
        filename: str = "clt_simulation.png",
    ) -> str:
        """Simulate the Central Limit Theorem for any distribution.

        Generates sampling distributions of the mean for different sample
        sizes, showing convergence to normality.

        Args:
            distribution: Base distribution — "norm", "exp", "unif", "binom",
                "pois", "chisq", "t".
            param1: First parameter.
            param2: Second parameter.
            sample_sizes: Comma-separated sample sizes (default "1,5,15,50").
            n_simulations: Number of simulation runs (default 1000).
            filename: Output PNG filename.

        Returns:
            JSON with plot path and normality test p-values for each n.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            sizes = [s.strip() for s in sample_sizes.split(",")]
            n_panels = len(sizes)

            param_map = {
                "norm": f"mean={param1}, sd={param2}",
                "exp": f"rate={param1}",
                "unif": f"min={param1}, max={param2}",
                "binom": f"size={int(param1)}, prob={param2}",
                "pois": f"lambda={param1}",
                "chisq": f"df={param1}",
                "t": f"df={param1}",
            }
            if distribution not in param_map:
                return json.dumps({"error": f"Unknown distribution: {distribution}"})
            params = param_map[distribution]

            sizes_r = f"c({','.join(sizes)})"
            code = (
                'library(jsonlite)\n'
                f'sizes <- {sizes_r}\n'
                f'nsim <- {n_simulations}\n'
                f'png("{out_path}", width = 300 * {n_panels}, height = 400, res = 150)\n'
                f'par(mfrow = c(1, {n_panels}))\n'
                'pvals <- numeric(length(sizes))\n'
                'for (i in seq_along(sizes)) {\n'
                '    n <- sizes[i]\n'
                '    means <- replicate(nsim, {\n'
                f'        x <- r{distribution}(n, {params})\n'
                '        mean(x)\n'
                '    })\n'
                '    hist(means, probability = TRUE, col = gray(0.9),\n'
                '        main = paste0("n=", n), xlab = "Sample Mean",\n'
                '        border = "white")\n'
                '    curve(dnorm(x, mean(means), sd(means)), add = TRUE,\n'
                '        col = "#E63946", lwd = 2)\n'
                '    pvals[i] <- shapiro.test(sample(means, min(5000, nsim)))$p.value\n'
                '}\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                f'    distribution = "{distribution}",\n'
                '    sample_sizes = sizes,\n'
                '    shapiro_p_values = round(pvals, 6),\n'
                f'    n_simulations = {n_simulations},\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=60)
            if rc != 0:
                return json.dumps({"error": stderr or "CLT simulation failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
