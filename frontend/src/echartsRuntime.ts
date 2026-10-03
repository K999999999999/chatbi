import { init, use } from 'echarts/core';
import { LineChart, BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, AriaComponent, DataZoomComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, AriaComponent, DataZoomComponent, SVGRenderer]);
export { init };
