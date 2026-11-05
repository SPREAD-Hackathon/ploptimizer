# Alignment plotting

Result pages contain no local file-upload controls. They display saved plots
supplied by the backend bundle, with coordinate downloads and actual source
labels. The W chromosome-only example draws existing reviewed alignment records;
it is not a NUCmer run. See [RESULTS_BUNDLE.md](RESULTS_BUNDLE.md).

Benchmark NUCmer plots and general per-base difference-event tables remain
uncollected. Missing measurements are not replaced with local previews.

The generic `website/dotplot.jsx` coordinate viewer and its synthetic tests remain
in the source for separate development. It is not mounted or bundled into the
production results site. It accepts 11-column `show-coords -THrl` tables with
1-based inclusive endpoints; this differs from the 0-based half-open reviewed
intervals used by the backend plot exporter. Do not interchange these formats.

The saved result plot and its endpoint score are independent: a straight
alignment line or rounded 100% identity does not prove an exact dedicated copy.
