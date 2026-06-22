export type CityOption = {
  label: string;
  value: string;
};

export const CITY_OPTIONS: CityOption[] = [
  { label: "北京", value: "北京" },
  { label: "上海", value: "上海" },
  { label: "广州", value: "广州" },
  { label: "深圳", value: "深圳" },
  { label: "天津", value: "天津" },
  { label: "重庆", value: "重庆" },
  { label: "杭州", value: "杭州" },
  { label: "南京", value: "南京" },
  { label: "苏州", value: "苏州" },
  { label: "武汉", value: "武汉" },
  { label: "成都", value: "成都" },
  { label: "西安", value: "西安" },
  { label: "郑州", value: "郑州" },
  { label: "长沙", value: "长沙" },
  { label: "济南", value: "济南" },
  { label: "青岛", value: "青岛" },
  { label: "福州", value: "福州" },
  { label: "厦门", value: "厦门" },
  { label: "合肥", value: "合肥" },
  { label: "南昌", value: "南昌" },
  { label: "南宁", value: "南宁" },
  { label: "昆明", value: "昆明" },
  { label: "贵阳", value: "贵阳" },
  { label: "太原", value: "太原" },
  { label: "石家庄", value: "石家庄" },
  { label: "呼和浩特", value: "呼和浩特" },
  { label: "哈尔滨", value: "哈尔滨" },
  { label: "长春", value: "长春" },
  { label: "沈阳", value: "沈阳" },
  { label: "海口", value: "海口" },
  { label: "兰州", value: "兰州" },
  { label: "银川", value: "银川" },
  { label: "西宁", value: "西宁" },
  { label: "乌鲁木齐", value: "乌鲁木齐" },
  { label: "宁波", value: "宁波" },
  { label: "无锡", value: "无锡" },
  { label: "佛山", value: "佛山" },
  { label: "东莞", value: "东莞" },
  { label: "泉州", value: "泉州" },
  { label: "温州", value: "温州" },
  { label: "常州", value: "常州" },
  { label: "香港", value: "香港" },
  { label: "澳门", value: "澳门" },
  { label: "台北", value: "台北" },
];

export function buildCityOptions(currentCity?: string | null): CityOption[] {
  const normalizedCity = currentCity?.trim();
  if (!normalizedCity) {
    return CITY_OPTIONS;
  }
  if (CITY_OPTIONS.some((option) => option.value === normalizedCity)) {
    return CITY_OPTIONS;
  }
  return [...CITY_OPTIONS, { label: `${normalizedCity}（已保存）`, value: normalizedCity }];
}
