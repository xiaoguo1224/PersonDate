import { codeToText, regionData } from "element-china-area-data";

export type ChinaAreaOption = {
  value: string;
  label: string;
  children?: ChinaAreaOption[];
};

export const chinaAreaOptions = regionData as ChinaAreaOption[];
const CITY_SEPARATOR_RE = /[\/\\|,，、\s-]+/g;
const CITY_SPLIT_RE = /[\/\\|,，、\s-]+/;

function normalizeForMatch(value: string) {
  return value.trim().replace(CITY_SEPARATOR_RE, "").replace(/市辖区/g, "");
}

function splitCityText(value: string) {
  return value
    .split(CITY_SPLIT_RE)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function findFirstLeafPath(nodes: ChinaAreaOption[], path: string[]): string[] | null {
  for (const node of nodes) {
    const nextPath = [...path, node.value];
    if (!node.children || node.children.length === 0) {
      return nextPath;
    }
    const leafPath = findFirstLeafPath(node.children, nextPath);
    if (leafPath) {
      return leafPath;
    }
  }
  return null;
}

function searchCityPath(
  nodes: ChinaAreaOption[],
  segments: string[],
  index: number,
  path: string[],
): string[] | null {
  for (const node of nodes) {
    const label = normalizeForMatch(node.label);
    const segment = normalizeForMatch(segments[index] ?? "");
    const matches = label.includes(segment) || segment.includes(label);

    if (matches) {
      const nextPath = [...path, node.value];

      if (index === segments.length - 1) {
        if (!node.children || node.children.length === 0) {
          return nextPath;
        }
        return findFirstLeafPath(node.children, nextPath);
      }

      if (node.children && node.children.length > 0) {
        const matchedPath = searchCityPath(node.children, segments, index + 1, nextPath);
        if (matchedPath) {
          return matchedPath;
        }
      }
    }

    if (node.children && node.children.length > 0) {
      const descendantPath = searchCityPath(node.children, segments, index, [...path, node.value]);
      if (descendantPath) {
        return descendantPath;
      }
    }
  }

  return null;
}

export function resolveCityPath(value?: string | null): string[] | null {
  if (!value || !value.trim()) {
    return null;
  }

  const segments = splitCityText(value);
  if (segments.length === 0) {
    return null;
  }

  const exactPath = searchCityPath(chinaAreaOptions, segments, 0, []);
  if (exactPath) {
    return exactPath;
  }

  const normalizedValue = normalizeForMatch(value);
  for (const province of chinaAreaOptions) {
    const provinceLabel = normalizeForMatch(province.label);
    if (provinceLabel.includes(normalizedValue) || normalizedValue.includes(provinceLabel)) {
      if (province.children && province.children.length > 0) {
        return findFirstLeafPath(province.children, [province.value]) ?? [province.value];
      }
      return [province.value];
    }
  }

  return null;
}

export function cityPathToText(path?: string[] | null): string | null {
  if (!path || path.length === 0) {
    return null;
  }

  return path
    .map((code) => codeToText[code] ?? code)
    .filter(Boolean)
    .join("/");
}

export function normalizeWeatherCityQuery(value?: string | null) {
  if (!value || !value.trim()) {
    return "";
  }

  return value.trim().replace(CITY_SEPARATOR_RE, "").replace(/市辖区/g, "");
}
