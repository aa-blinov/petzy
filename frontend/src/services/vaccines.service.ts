import api from './api';

export interface VaccineGroup {
  key: string;
  /** Short, for a row and a button: «Комплексная для собак». */
  label: string;
  /** What it covers, when the label does not say. */
  detail: string;
  species: string[];
}

export interface VaccineProduct {
  name: string;
  species: string[];
  protects: string;
}

export interface VaccineCatalog {
  groups: VaccineGroup[];
  products: VaccineProduct[];
}

export const vaccinesService = {
  async catalog(): Promise<VaccineCatalog> {
    const response = await api.get<VaccineCatalog>('/vaccines/catalog');
    return response.data;
  },
};
