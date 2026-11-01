export type Scenario = 'rcp45' | 'rcp85';
export type Period = 'mid' | 'late';

export interface ClimateCellProperties extends Record<string, unknown> {
  cell_id: string | number;
  population_2020: number;
  warming_rcp45_mid_p10: number;
  warming_rcp45_mid_p50: number;
  warming_rcp45_mid_p90: number;
  warming_rcp45_late_p10: number;
  warming_rcp45_late_p50: number;
  warming_rcp45_late_p90: number;
  warming_rcp85_mid_p10: number;
  warming_rcp85_mid_p50: number;
  warming_rcp85_mid_p90: number;
  warming_rcp85_late_p10: number;
  warming_rcp85_late_p50: number;
  warming_rcp85_late_p90: number;
}
