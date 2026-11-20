# -*- coding: utf-8 -*-
"""中国机构 → 省市权威映射规则。

背景：旧的 CHINA_LOCATION_RULES 把省份级词（jiangsu/zhejiang/shandong 等）
直接映射到单一城市（徐州/杭州/济南），且用裸子串 "xian" 匹配，
导致华西医院（West China Hospital, Sichuan University）被误判为陕西西安、
苏州大学被误判为徐州、温州被误判为杭州等系统性错误。

本模块按“特异性从高到低”排序，命中第一条即返回：
  1. 地区（港澳台）
  2. 歧义特例（暨南大学、齐鲁青岛院区、中国医药大学等）
  3. 具体医院/高校（含城市信息的专名）
  4. 城市名关键词
  5. 省份名 → 省会（兜底）

所有匹配使用字母数字边界，避免 "xian" 命中 "xiangya"、
"jinan" 命中 "jinan university"（暨南大学在广州）等子串误判。

供 build-frontend-data.py 与城市标签修正脚本共用，保证各管线推断一致。
"""
import re

# (省份, 城市, [关键词]) —— 顺序即优先级，越靠前越具体
LOCATION_RULES = [
    # ---------- 港澳台（含分校/合作医院特例，须早于地区词）----------
    ("广东", "深圳", [
        "hong kong-shenzhen", "hongkong university shenzhen",
        "university of hong kong shenzhen", "hong kong shenzhen hospital",
    ]),  # 港大深圳医院在深圳，不在香港
    # 解放军总医院海南医院在三亚（须早于“hainan hospital→海口”兜底）
    ("海南", "三亚", ["hainan hospital of chinese pla", "hainan hospital of pla"]),
    ("台湾", "台湾", ["college of medicine, china medical university"]),  # 台湾中国医药大学
    ("海南", "海口", ["hainan hospital"]),
    ("香港", "香港", ["hong kong", "hongkong"]),
    ("台湾", "台湾", [
        "taiwan", "taipei", "kaohsiung", "taichung", "tainan", "hsinchu",
        "chang gung", "chang-gung", "yang-ming", "yang ming", "shin kong",
        "tri-service", "tri service", "veterans general", "national taiwan",
        "taipei medical university", "china medical university hospital",
        "fu jen", "soochow university taiwan", "kaohsiung medical",
    ]),

    # ---------- 歧义特例（必须早于泛化词）----------
    ("广东", "广州", ["jinan university", "ji nan university"]),  # 暨南大学
    ("山东", "青岛", ["qilu hospital (qingdao)", "qilu hospital qingdao"]),
    ("辽宁", "沈阳", ["china medical university"]),  # 中国医科大学（沈阳）
    # 医院所在城市优先于校名：青大附院烟台毓璜顶/泰安中心分别在烟台、泰安
    ("山东", "烟台", ["yantai", "yu huang ding", "yuhuangding"]),
    ("山东", "泰安", ["tai'an", "taian", "taian city central"]),
    # 上海新华医院 vs 浙江新华医院
    ("浙江", "杭州", ["xinhua hospital of zhejiang", "xinhua hospital zhejiang"]),
    # 空军特色医学中心在北京；西部战区空军医院在成都；均早于“空军军医大学→西安”
    ("北京", "北京", ["air force medical center", "air force general hospital"]),
    ("四川", "成都", ["air force hospital of western theater", "western theater command air force"]),
    # 江苏师范大学（JSNU）在徐州，不在南京
    ("江苏", "徐州", ["jiangsu normal university", "jsnu"]),
    # 医院所在城市优先于校名：无锡人民医院（南医大附属）在无锡，非南京
    ("江苏", "无锡", ["wuxi people's hospital", "wuxi municipal", "wuxi second people", "wuxi third people"]),
    # 同名地名/substr 特例：安徽宿州市（Suzhou）非江苏苏州；瑞金无锡分院归属上海总院
    ("安徽", "宿州", ["suzhou hospital of anhui", "suzhou municipal hospital of anhui"]),
    ("上海", "上海", ["wuxi branch of ruijin", "ruijin hospital wuxi"]),
    # 四川骨科医院+深圳公司混合实体，按医院本体保留四川成都
    ("四川", "成都", ["sichuan provincial orthopedic hospital"]),

    # ---------- 具体医院/高校：华北 ----------
    ("北京", "北京", [
        "peking university", "peking union medical college", "pumch",
        "xuanwu hospital", "capital medical university", "beijing tongren",
        "beijing hospital", "beijing tiantan", "tiantan hospital",
        "chinese pla general hospital", "pla general hospital",
        "first medical center of pla", "general hospital of pla",
        "guang'anmen hospital", "guang an men hospital",
        "china-japan friendship hospital", "beijing friendship hospital",
        "beijing chaoyang hospital", "beijing anzhen", "beijing anding",
        "peking university first hospital", "peking university people's hospital",
        "beijing university of chinese medicine", "beijing normal university",
        "chinese academy of medical sciences", "beijing institute",
        "peking union", "tsinghua university", "beijing university",
    ]),
    ("天津", "天津", ["tianjin", "tientsin"]),
    ("河北", "石家庄", [
        "hebei medical university", "hebei provincial", "shijiazhuang",
        "fourth hospital of hebei", "hebei university",
    ]),
    ("山西", "太原", [
        "shanxi medical university", "first hospital of shanxi", "taiyuan",
        "shanxi provincial", "shanxi university",
    ]),
    ("内蒙古", "呼和浩特", ["inner mongolia", "innermongolia", "hohhot"]),

    # ---------- 具体医院/高校：东北 ----------
    ("黑龙江", "哈尔滨", ["harbin", "heilongjiang"]),
    ("吉林", "长春", [
        "jilin university", "changchun", "jilin provincial", "jilin city",
        "beihua university", "yanbian university",
    ]),
    ("辽宁", "沈阳", [
        "shenyang", "shengjing hospital", "liaoning", "china medical university",
        "first affiliated hospital of china medical",
    ]),
    ("辽宁", "大连", ["dalian"]),

    # ---------- 具体医院/高校：华东 ----------
    ("上海", "上海", [
        "shanghai", "fudan university", "huashan hospital", "huashan rare disease",
        "ruijin hospital", "zhongshan hospital", "renji hospital",
        "changhai hospital", "xinhua hospital", "shanghai chest hospital",
        "shanghai east hospital", "shanghai general hospital",
        "shanghai medical college", "shanghai jiao tong university",
        "shanghai university", "tongji university", "second military medical",
        "navy medical university", "chinese academy of sciences shanghai",
        "national center for neurological disorders",
        "national centre for neurological disorders",
        "national center for neurological diseases",
        "national centre for neurological diseases",
        "jing'an district centre hospital", "xinhua hospital affiliated",
        "shanghai neurological", "huashan hospital fudan",
    ]),
    ("江苏", "南京", [
        "nanjing", "drum tower hospital", "southeast university",
        "jiangsu province hospital", "jiangsu provincial people's hospital",
        "nanjing medical university", "nanjing university",
    ]),
    ("江苏", "苏州", ["soochow", "suzhou"]),
    ("江苏", "无锡", ["wuxi"]),
    ("江苏", "徐州", ["xuzhou"]),
    ("江苏", "常州", ["changzhou"]),
    ("江苏", "南通", ["nantong"]),
    ("江苏", "扬州", ["yangzhou"]),
    ("江苏", "镇江", ["zhenjiang"]),
    ("浙江", "杭州", [
        "hangzhou", "zhejiang university", "zhejiang provincial",
        "zhejiang chinese medical university", "zhejiang university of technology",
    ]),
    ("浙江", "温州", ["wenzhou"]),
    ("浙江", "宁波", ["ningbo"]),
    ("浙江", "金华", ["jinhua"]),
    ("山东", "济南", [
        "jinan", "qilu hospital", "shandong university", "shandong provincial",
        "shandong first medical university", "shandong first medical",
        "qianfoshan", "shandong institute", "shandong university of traditional",
        "shandong medical university", "cheeloo", "shandong normal university",
    ]),
    ("山东", "青岛", ["qingdao"]),
    ("山东", "济宁", ["jining"]),
    ("山东", "滨州", ["binzhou"]),
    ("山东", "烟台", ["yantai"]),
    ("山东", "潍坊", ["weifang"]),
    ("山东", "临沂", ["linyi"]),
    ("安徽", "合肥", ["hefei", "anhui", "ustc", "university of science and technology of china"]),
    ("福建", "福州", ["fuzhou", "fujian", "fujian medical university"]),
    ("福建", "厦门", ["xiamen"]),
    ("江西", "南昌", ["nanchang", "jiangxi"]),

    # ---------- 具体医院/高校：华中 ----------
    ("河南", "郑州", [
        "zhengzhou", "henan", "zhengzhou university", "henan provincial",
        "henan institute", "henan university", "luoyang", "xinxiang",
        "bgi college",
    ]),
    ("湖北", "武汉", [
        "wuhan", "tongji hospital", "tongji medical college", "huazhong university",
        "hust", "renmin hospital of wuhan", "wuhan university",
        "union hospital tongji medical", "hubei", "central china normal",
    ]),
    ("湖北", "襄阳", ["xiangyang"]),
    ("湖北", "宜昌", ["yichang"]),
    ("湖南", "长沙", [
        "changsha", "xiangya", "central south university", "hunan",
        "hunan children's hospital", "hunan normal university",
    ]),

    # ---------- 具体医院/高校：华南 ----------
    ("广东", "广州", [
        "guangzhou", "sun yat-sen", "sun yat sen", "nanfang hospital",
        "southern medical university", "guangdong", "guangzhou university",
        "first affiliated hospital of guangzhou", "guangdong provincial",
        "guangdong pharmaceutical", "guangzhou medical university",
        "guangdong key laboratory", "national key clinical department",
        "guangdong university", "jinan university", "guangdong medical university",
    ]),
    ("广东", "深圳", ["shenzhen"]),
    ("广东", "珠海", ["zhuhai"]),
    ("广东", "佛山", ["foshan"]),
    ("广东", "东莞", ["dongguan"]),
    ("广西", "南宁", ["nanning", "guangxi", "guangxi medical university"]),
    ("广西", "桂林", ["guilin"]),
    ("海南", "海口", ["haikou", "hainan"]),
    ("海南", "琼海", ["qionghai", "lecheng"]),

    # ---------- 具体医院/高校：西南 ----------
    ("四川", "成都", [
        "west china", "sichuan university", "chengdu", "sichuan provincial",
        "sichuan academy of medical science", "sichuan normal university",
        "chengdu university", "sichuan", "west china school of nursing",
    ]),
    ("四川", "绵阳", ["mianyang"]),
    ("四川", "南充", ["nanchong"]),
    ("重庆", "重庆", ["chongqing"]),
    ("贵州", "贵阳", ["guiyang", "guizhou medical university", "guizhou"]),
    ("贵州", "遵义", ["zunyi"]),
    ("云南", "昆明", ["kunming", "yunnan"]),
    ("西藏", "拉萨", ["lhasa", "tibet"]),

    # ---------- 具体医院/高校：西北 ----------
    ("陕西", "西安", [
        "tangdu hospital", "air force medical university", "fourth military medical university",
        "xijing hospital", "xi'an jiaotong", "xian jiaotong", "xi'an", "xian",
        "shaanxi", "shaanxi normal university", "northwest university",
        "air force medical", "fourth military", "xi'an medical university",
    ]),
    ("陕西", "咸阳", ["xianyang"]),
    ("甘肃", "兰州", ["lanzhou", "gansu"]),
    ("青海", "西宁", ["xining", "qinghai"]),
    ("宁夏", "银川", ["yinchuan", "ningxia"]),
    ("新疆", "乌鲁木齐", ["urumqi", "xinjiang"]),

    # ---------- 省份兜底（最后）----------
    ("北京", "北京", ["beijing", "peking"]),
    ("上海", "上海", ["shanghai"]),
    ("天津", "天津", ["tianjin"]),
    ("重庆", "重庆", ["chongqing"]),
    ("江苏", "南京", ["jiangsu"]),
    ("浙江", "杭州", ["zhejiang"]),
    ("山东", "济南", ["shandong"]),
    ("河南", "郑州", ["henan"]),
    ("湖北", "武汉", ["hubei"]),
    ("湖南", "长沙", ["hunan"]),
    ("广东", "广州", ["guangdong"]),
    ("福建", "福州", ["fujian"]),
    ("江西", "南昌", ["jiangxi"]),
    ("河北", "石家庄", ["hebei"]),
    ("山西", "太原", ["shanxi"]),
    ("安徽", "合肥", ["anhui"]),
    ("广西", "南宁", ["guangxi"]),
    ("云南", "昆明", ["yunnan"]),
    ("贵州", "贵阳", ["guizhou"]),
    ("甘肃", "兰州", ["gansu"]),
    ("陕西", "西安", ["shaanxi"]),
    ("新疆", "乌鲁木齐", ["xinjiang"]),
    ("内蒙古", "呼和浩特", ["inner mongolia"]),
    ("宁夏", "银川", ["ningxia"]),
    ("青海", "西宁", ["qinghai"]),
    ("海南", "海口", ["hainan"]),
]


def norm_text(value):
    """归一化机构文本：小写、压缩空白。"""
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _term_in_text(text, term):
    """带字母数字边界的关键词匹配，避免裸子串误命中。"""
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def infer_china_location(institution, raw_affiliations=None):
    """根据机构名推断省份/城市。返回 {"province":..., "city":...}。

    优先只看规范化机构名（canonical affiliation）；仅当机构名无信号时，
    才用 raw affiliations 兜底，避免专家因某篇合作论文里出现他院地名而被误判。
    """
    primary = norm_text(institution)
    if primary:
        for province, city, terms in LOCATION_RULES:
            if any(_term_in_text(primary, t) for t in terms):
                return {"province": province, "city": city}
    raws = [norm_text(x) for x in (raw_affiliations or []) if x]
    for province, city, terms in LOCATION_RULES:
        if any(any(_term_in_text(r, t) for t in terms) for r in raws):
            return {"province": province, "city": city}
    return {"province": "未识别", "city": ""}
