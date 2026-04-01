"""Clustering tools — k-means, hierarchical, silhouette analysis."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_clustering_tools(mcp: FastMCP) -> None:
    """Register clustering analysis tools with the MCP server."""

    @mcp.tool()
    async def kmeans_clustering(
        ctx: Context,
        file_path: str,
        k: int = 3,
        columns: str = "",
        filename: str = "kmeans.png",
        max_k: int = 10,
    ) -> str:
        """Run k-means clustering with elbow plot and cluster visualization.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            k: Number of clusters (default 3).
            columns: Comma-separated numeric columns to use (empty = all numeric).
            filename: Output plot filename.
            max_k: Max k for elbow plot (default 10).

        Returns:
            JSON with cluster centers, sizes, within-SS, and plot path.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            col_filter = ""
            if columns.strip():
                cols = [c.strip() for c in columns.split(",")]
                col_r = ", ".join(f'"{c}"' for c in cols)
                col_filter = f'nums <- df[, c({col_r}), drop = FALSE]\n'
            else:
                col_filter = 'nums <- df[, sapply(df, is.numeric), drop = FALSE]\n'

            code = (
                'library(jsonlite)\nlibrary(cluster)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                'nums <- na.omit(nums)\n'
                'scaled <- scale(nums)\n'
                f'# Elbow analysis\n'
                f'wss <- sapply(1:{max_k}, function(k)\n'
                '    kmeans(scaled, k, nstart = 10)$tot.withinss)\n'
                f'# Fit with chosen k\n'
                f'km <- kmeans(scaled, {k}, nstart = 25)\n'
                'sil <- silhouette(km$cluster, dist(scaled))\n'
                'avg_sil <- mean(sil[, 3])\n'
                f'png("{out_path}", width = 1200, height = 500, res = 150)\n'
                'par(mfrow = c(1, 2))\n'
                f'plot(1:{max_k}, wss, type = "b", pch = 19, col = "#457B9D",\n'
                '    xlab = "Number of Clusters (k)", ylab = "Total Within SS",\n'
                '    main = "Elbow Method")\n'
                f'abline(v = {k}, col = "#E63946", lty = 2, lwd = 2)\n'
                'if (ncol(scaled) >= 2) {\n'
                '    pca <- prcomp(scaled)\n'
                '    plot(pca$x[,1], pca$x[,2], col = km$cluster + 1, pch = 19,\n'
                '        xlab = "PC1", ylab = "PC2",\n'
                '        main = paste0("K-Means (k=", ' + str(k) + ', ", sil=",\n'
                '            round(avg_sil, 3), ")"))\n'
                '    # Plot centers projected\n'
                '    centers_pca <- predict(pca, km$centers)\n'
                '    points(centers_pca[,1], centers_pca[,2],\n'
                '        pch = 4, cex = 2, lwd = 3, col = "black")\n'
                '}\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                f'    k = {k},\n'
                '    sizes = as.numeric(km$size),\n'
                '    within_ss = km$tot.withinss,\n'
                '    between_ss = km$betweenss,\n'
                '    avg_silhouette = round(avg_sil, 4),\n'
                '    centers = as.data.frame(km$centers),\n'
                '    elbow_wss = wss,\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=60)
            if rc != 0:
                return json.dumps({"error": stderr or "K-means failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def hierarchical_clustering(
        ctx: Context,
        file_path: str,
        k: int = 3,
        method: str = "ward.D2",
        columns: str = "",
        filename: str = "dendrogram.png",
    ) -> str:
        """Run hierarchical clustering and produce a dendrogram.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            k: Number of clusters to cut the dendrogram into (default 3).
            method: Linkage method — "ward.D2" (default), "complete",
                    "average", "single", "centroid".
            columns: Comma-separated numeric columns (empty = all numeric).
            filename: Output dendrogram filename.

        Returns:
            JSON with cluster sizes, cophenetic correlation, and plot path.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            col_filter = ""
            if columns.strip():
                cols = [c.strip() for c in columns.split(",")]
                col_r = ", ".join(f'"{c}"' for c in cols)
                col_filter = f'nums <- df[, c({col_r}), drop = FALSE]\n'
            else:
                col_filter = 'nums <- df[, sapply(df, is.numeric), drop = FALSE]\n'

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                'nums <- na.omit(nums)\n'
                'scaled <- scale(nums)\n'
                'd <- dist(scaled)\n'
                f'hc <- hclust(d, method = "{method}")\n'
                f'clusters <- cutree(hc, k = {k})\n'
                'coph <- cor(d, cophenetic(hc))\n'
                f'png("{out_path}", width = 1200, height = 600, res = 150)\n'
                'plot(hc, labels = FALSE, hang = -1,\n'
                f'    main = paste0("Dendrogram — {method} (k={k})"))\n'
                f'rect.hclust(hc, k = {k}, border = 2:({k}+1))\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                f'    method = "{method}", k = {k},\n'
                '    sizes = as.numeric(table(clusters)),\n'
                '    cophenetic_corr = round(coph, 4),\n'
                '    height_range = range(hc$height),\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=60)
            if rc != 0:
                return json.dumps({"error": stderr or "Hclust failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
