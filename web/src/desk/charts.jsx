// Wykresy: Chart.js (MIT) z kolorami z motywu Astryx. Jeden komponent, dane przychodzą jako propsy (bez własnego pobierania).
// Płótno ma rolę „img” i opis tekstowy; ta sama treść jest też w tabeli obok wykresu, więc wykres nie jest jedynym nośnikiem informacji.
import React, { useEffect, useMemo, useRef } from "react";
import { BarController, BarElement, CategoryScale, Chart as ChartJS, Filler, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip } from "chart.js";
import { VStack } from "@astryxdesign/core/Layout";
import { useTheme } from "@astryxdesign/core/theme";

ChartJS.register(BarController, BarElement, CategoryScale, Filler, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip);

export const SERIES = ["blue", "orange", "green", "purple"];

/**
 * spec: { type: "bar"|"line", labels: string[], datasets: [{ label, data, axis?: "y"|"y2", color?: nazwa serii }], stacked?, height }
 * Dwie osie (y, y2) są używane, gdy zestawy mają różne skale (materiały i skierowania).
 */
export function Chart({ spec, label, height = 220, width }) {
  const canvas = useRef(null);
  const chart = useRef(null);
  const { tokens } = useTheme();
  const text = tokens["--color-text-secondary"];
  const grid = tokens["--color-border"];
  const color = (name, i) => tokens[`--color-data-categorical-${name || SERIES[i % SERIES.length]}`];

  useEffect(() => {
    if (!canvas.current) return undefined;
    const twoAxes = spec.datasets.some((d) => d.axis === "y2");
    const scale = (title, position, onlyGrid) => ({
      position,
      beginAtZero: true,
      grace: "10%",
      ticks: { color: text, precision: 0, font: { family: tokens["--font-family-body"] } },
      grid: { color: grid, drawOnChartArea: onlyGrid },
      title: { display: !!title, text: title, color: text },
    });
    const config = {
      type: spec.type,
      data: {
        labels: spec.labels,
        datasets: spec.datasets.map((d, i) => ({
          label: d.label,
          data: d.data,
          yAxisID: d.axis || "y",
          backgroundColor: color(d.color, i),
          borderColor: color(d.color, i),
          borderWidth: spec.type === "line" ? 2 : 0,
          borderRadius: 3,
          tension: 0.25,
          pointRadius: spec.type === "line" ? 3 : 0,
          maxBarThickness: 44,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: spec.datasets.length > 1, position: "bottom", labels: { color: text, boxWidth: 12, font: { family: tokens["--font-family-body"] } } },
          tooltip: { callbacks: spec.tooltip ? { afterBody: spec.tooltip } : {} },
        },
        scales: {
          x: { stacked: !!spec.stacked, ticks: { color: text, maxRotation: 0, autoSkip: true, font: { family: tokens["--font-family-body"] } }, grid: { display: false } },
          y: { ...scale(spec.yTitle, "left", true), stacked: !!spec.stacked },
          ...(twoAxes ? { y2: scale(spec.y2Title, "right", false) } : {}),
        },
      },
    };
    if (spec.mini) {
      config.options.plugins = { legend: { display: false }, tooltip: { enabled: false } };
      config.options.scales = { x: { display: false }, y: { display: false, beginAtZero: true } };
      config.options.layout = { padding: 2 };
      config.options.events = [];
    }
    chart.current?.destroy();
    chart.current = new ChartJS(canvas.current, config);
    return () => {
      chart.current?.destroy();
      chart.current = null;
    };
  }, [spec, text, grid]);

  return (
    <VStack height={height} width={width}>
      <canvas ref={canvas} role="img" aria-label={label} data-chart={spec.type} />
    </VStack>
  );
}

/** Mały wykres liniowy bez osi (skrót w nagłówku kolejki). */
export function Sparkline({ values, label, width = 96, height = 28 }) {
  const spec = useMemo(() => ({ type: "line", mini: true, labels: values.map((_, i) => String(i + 1)), datasets: [{ label, data: values, color: "blue" }] }), [values.join(",")]);
  if (!values.length) return null;
  return <Chart spec={spec} label={label} height={height} width={width} />;
}
