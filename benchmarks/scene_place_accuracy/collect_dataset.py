"""Build the locked Wikimedia Commons datasets for scene-place accuracy.

This intentionally uses the MediaWiki Action API (not page scraping) and only
the Python standard library.  Re-running is safe: already-locked valid images
are retained and only missing rows are collected.
"""
import argparse
import csv
import hashlib
import html
import json
import mimetypes
import re
import shutil
import sys
import time
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
API = "https://commons.wikimedia.org/w/api.php"
AGENT = "dx-all-scene-place-benchmark/1.0 (dataset collection; contact: benchmark@example.invalid)"
DELAY = 0.20
MIN_W, MIN_H = 800, 600
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
FOREIGN_TERMS = ("luxembourg", "somerset", "united kingdom", " england", " uk", "france", "germany", "japan", "china", "usa", "united states")
SUBJECT_TERMS = ("squirrel", "chipmunk", "animal", "bird", "cat", "dog", "food", "dish", "portrait", "selfie", "flower", "insect", "tourists")

# Kept in the same sequence as their retired entries, so DIV numbers remain stable.
REPLACEMENTS = {
    "petite_france": ("garden_of_morning_calm", "아침고요수목원", ["아침고요수목원", "The Garden of Morning Calm", "Garden of Morning Calm"], "The Garden of Morning Calm", "garden", "Gyeonggi"),
    "gunsan_railroad_village": ("gunsan_modern_history_museum", "군산근대역사박물관", ["군산근대역사박물관", "Gunsan Modern History Museum"], "Gunsan Modern History Museum", "museum", "Jeonbuk"),
    "jindo_miracle_sea_road": ("damyang_juknokwon", "담양 죽녹원", ["담양 죽녹원", "Juknokwon", "Juknokwon Bamboo Forest"], "Juknokwon Bamboo Forest", "natural_attraction", "Jeonnam"),
    "seomjin_river_train_village": ("suncheon_bay_national_garden", "순천만국가정원", ["순천만국가정원", "Suncheon Bay National Garden"], "Suncheon Bay National Garden", "garden", "Jeonnam"),
    "geoje_hakdong_beach": ("oedo_botania", "외도 보타니아", ["외도 보타니아", "Oedo Botania", "Oedo-Botania"], "Oedo Botania", "garden", "Gyeongnam"),
    "gwangju_may_18": ("seodaemun_prison_history_hall", "서대문형무소역사관", ["서대문형무소역사관", "Seodaemun Prison History Hall"], "Seodaemun Prison History Hall", "heritage", "Seoul"),
    "ganghwa_dolmen": ("ojukheon", "오죽헌", ["오죽헌", "Ojukheon", "Ojukheon House"], "Ojukheon Gangneung", "heritage", "Gangwon"),
    "chuncheon_soyangan_skywalk": ("seonamsa", "선암사", ["선암사", "Seonamsa", "Seonamsa Temple"], "Seonamsa Temple Suncheon", "temple", "Jeonnam"),
    "wonju_sogeumsan": ("jinju_castle", "진주성", ["진주성", "Jinju Castle", "Jinjuseong"], "Jinju Castle Korea", "fortress", "Gyeongnam"),
    "uljin_bulgyeongsa": ("woljeonggyo", "월정교", ["월정교", "Woljeonggyo", "Woljeong Bridge"], "Woljeonggyo Gyeongju", "bridge", "Gyeongbuk"),
}

# id, Korean official name, accepted Korean/English aliases, Commons query, category, region
DIVERSITY = [
 ("gyeongbokgung","경복궁",["경복궁","Gyeongbokgung","Gyeongbokgung Palace"],"Gyeongbokgung Palace","palace","Seoul"),
 ("changdeokgung","창덕궁",["창덕궁","Changdeokgung","Changdeokgung Palace"],"Changdeokgung Palace","palace","Seoul"),
 ("changgyeonggung","창경궁",["창경궁","Changgyeonggung","Changgyeonggung Palace"],"Changgyeonggung Palace","palace","Seoul"),
 ("deoksugung","덕수궁",["덕수궁","Deoksugung","Deoksugung Palace"],"Deoksugung Palace","palace","Seoul"),
 ("jongmyo","종묘",["종묘","Jongmyo Shrine","Jongmyo"],"Jongmyo Shrine","heritage","Seoul"),
 ("n_seoul_tower","N서울타워",["N서울타워","N Seoul Tower","Namsan Seoul Tower"],"N Seoul Tower","tower","Seoul"),
 ("ddp","동대문디자인플라자",["동대문디자인플라자","DDP","Dongdaemun Design Plaza"],"Dongdaemun Design Plaza","modern_architecture","Seoul"),
 ("seoul_city_hall","서울특별시청",["서울특별시청","서울시청","Seoul City Hall"],"Seoul City Hall building","modern_architecture","Seoul"),
 ("seoul_olympic_park","올림픽공원",["올림픽공원","Olympic Park","Seoul Olympic Park"],"Olympic Park Seoul","park","Seoul"),
 ("bukchon_hanok_village","북촌한옥마을",["북촌한옥마을","Bukchon Hanok Village"],"Bukchon Hanok Village","traditional_village","Seoul"),
 ("incheon_bridge","인천대교",["인천대교","Incheon Bridge"],"Incheon Bridge","bridge","Incheon"),
 ("songdo_central_park","송도센트럴파크",["송도센트럴파크","Songdo Central Park"],"Songdo Central Park","park","Incheon"),
 ("suwon_hwaseong","수원화성",["수원화성","Hwaseong Fortress","Suwon Hwaseong"],"Hwaseong Fortress","fortress","Gyeonggi"),
 ("korean_folk_village","한국민속촌",["한국민속촌","Korean Folk Village"],"Korean Folk Village","tourist_facility","Gyeonggi"),
 ("petite_france","쁘띠프랑스",["쁘띠프랑스","Petite France"],"Petite France Korea","tourist_facility","Gyeonggi"),
 ("nami_island","남이섬",["남이섬","Nami Island","Namiseom"],"Nami Island Korea","island","Gangwon"),
 ("seoraksan","설악산",["설악산","Seoraksan","Seoraksan National Park"],"Seoraksan","mountain","Gangwon"),
 ("gangneung_gyeongpo_beach","경포해변",["경포해변","경포대해수욕장","Gyeongpo Beach"],"Gyeongpo Beach","beach","Gangwon"),
 ("jeongdongjin","정동진",["정동진","Jeongdongjin"],"Jeongdongjin","natural_attraction","Gangwon"),
 ("pyeongchang_alpensia","알펜시아",["알펜시아","Alpensia Resort"],"Alpensia Resort","tourist_facility","Gangwon"),
 ("woljeongsa","월정사",["월정사","Woljeongsa","Woljeongsa Temple"],"Woljeongsa Temple","temple","Gangwon"),
 ("andong_hahoe","안동하회마을",["안동하회마을","하회마을","Hahoe Folk Village"],"Hahoe Folk Village","traditional_village","Gyeongbuk"),
 ("bulguksa","불국사",["불국사","Bulguksa","Bulguksa Temple"],"Bulguksa","temple","Gyeongbuk"),
 ("seokguram","석굴암",["석굴암","Seokguram Grotto","Seokguram"],"Seokguram Grotto","heritage","Gyeongbuk"),
 ("cheomseongdae","첨성대",["첨성대","Cheomseongdae","Cheomseongdae Observatory"],"Cheomseongdae","heritage","Gyeongbuk"),
 ("donggung_wolji","동궁과 월지",["동궁과 월지","안압지","Donggung and Wolji","Anapji"],"Donggung and Wolji","heritage","Gyeongbuk"),
 ("pohang_space_walk","스페이스워크",["스페이스워크","Space Walk"],"Space Walk Pohang","modern_architecture","Gyeongbuk"),
 ("ulleungdo","울릉도",["울릉도","Ulleungdo","Ulleung Island"],"Ulleungdo","island","Gyeongbuk"),
 ("dokdo","독도",["독도","Dokdo","Liancourt Rocks"],"Dokdo Korea","island","Gyeongbuk"),
 ("haeinsa","해인사",["해인사","Haeinsa","Haeinsa Temple"],"Haeinsa","temple","Gyeongnam"),
 ("tongyeong_cable_car","통영케이블카",["통영케이블카","Tongyeong Cable Car"],"Tongyeong Cable Car","tourist_facility","Gyeongnam"),
 ("windy_hill","바람의 언덕",["바람의 언덕","Windy Hill"],"Windy Hill Geoje","natural_attraction","Gyeongnam"),
 ("jinhae_gunhangje","진해군항제",["진해군항제","Jinhae Gunhangje Festival"],"Jinhae cherry blossom","festival_site","Gyeongnam"),
 ("busan_gwangandaegyo","광안대교",["광안대교","Gwangan Bridge","Gwangandaegyo"],"Gwangan Bridge","bridge","Busan"),
 ("haeundae_beach","해운대해수욕장",["해운대해수욕장","Haeundae Beach"],"Haeundae Beach","beach","Busan"),
 ("gamcheon_culture_village","감천문화마을",["감천문화마을","Gamcheon Culture Village"],"Gamcheon Culture Village","traditional_village","Busan"),
 ("haedong_yonggungsa","해동용궁사",["해동용궁사","Haedong Yonggungsa"],"Haedong Yonggungsa","temple","Busan"),
 ("busan_tower","부산타워",["부산타워","Busan Tower"],"Busan Tower","tower","Busan"),
 ("taejongdae","태종대",["태종대","Taejongdae"],"Taejongdae","natural_attraction","Busan"),
 ("daejeon_expo_bridge","엑스포다리",["엑스포다리","Expo Bridge"],"Expo Bridge Daejeon","bridge","Daejeon"),
 ("hanbat_arboretum","한밭수목원",["한밭수목원","Hanbat Arboretum"],"Hanbat Arboretum","park","Daejeon"),
 ("cheongnamdae","청남대",["청남대","Cheongnamdae"],"Cheongnamdae","heritage","Chungbuk"),
 ("beopjusa","법주사",["법주사","Beopjusa","Beopjusa Temple"],"Beopjusa","temple","Chungbuk"),
 ("danyang_dodam_sambong","도담삼봉",["도담삼봉","Dodamsambong Peaks"],"Dodamsambong","natural_attraction","Chungbuk"),
 ("gongju_gongsanseong","공주 공산성",["공주 공산성","Gongsanseong Fortress"],"Gongsanseong Fortress","fortress","Chungnam"),
 ("buyeo_baesanjeong","부여 부소산성",["부여 부소산성","Busosanseong Fortress"],"Busosanseong Fortress","fortress","Chungnam"),
 ("taean_anmyeondo","안면도",["안면도","Anmyeondo","Anmyeon Island"],"Anmyeondo","island","Chungnam"),
 ("jeonju_hanok_village","전주한옥마을",["전주한옥마을","Jeonju Hanok Village"],"Jeonju Hanok Village","traditional_village","Jeonbuk"),
 ("jeonju_pungnammun","풍남문",["풍남문","Pungnammun Gate"],"Pungnammun","heritage","Jeonbuk"),
 ("naejangsan","내장산",["내장산","Naejangsan","Naejangsan National Park"],"Naejangsan","mountain","Jeonbuk"),
 ("gunsan_railroad_village","경암동철길마을",["경암동철길마을","Gyeongam Railroad Village"],"Gyeongam Railroad Village","tourist_facility","Jeonbuk"),
 ("suncheon_bay","순천만습지",["순천만습지","순천만","Suncheon Bay Wetland Reserve"],"Suncheon Bay Wetland","natural_attraction","Jeonnam"),
 ("yeosu_expo","여수세계박람회장",["여수세계박람회장","Yeosu Expo"],"Yeosu Expo","tourist_facility","Jeonnam"),
 ("hyangiram","향일암",["향일암","Hyangiram"],"Hyangiram","temple","Jeonnam"),
 ("boseong_tea_fields","보성녹차밭",["보성녹차밭","Boseong Green Tea Fields"],"Boseong tea fields","natural_attraction","Jeonnam"),
 ("jindo_miracle_sea_road","진도 신비의 바닷길",["진도 신비의 바닷길","Jindo Sea Parting"],"Jindo sea parting","natural_attraction","Jeonnam"),
 ("mudeungsan","무등산",["무등산","Mudeungsan","Mudeungsan National Park"],"Mudeungsan","mountain","Gwangju"),
 ("asia_culture_center","국립아시아문화전당",["국립아시아문화전당","Asia Culture Center"],"Asia Culture Center Gwangju","modern_architecture","Gwangju"),
 ("ulsan_daewangam","대왕암공원",["대왕암공원","Daewangam Park"],"Daewangam Park","park","Ulsan"),
 ("ulsan_grand_park","울산대공원",["울산대공원","Ulsan Grand Park"],"Ulsan Grand Park","park","Ulsan"),
 ("seomjin_river_train_village","섬진강기차마을",["섬진강기차마을","Seomjin River Train Village"],"Seomjin River Train Village","tourist_facility","Jeonnam"),
 ("hallasan","한라산",["한라산","Hallasan","Hallasan National Park"],"Hallasan","mountain","Jeju"),
 ("seongsan_ilchulbong","성산일출봉",["성산일출봉","Seongsan Ilchulbong","Seongsan Sunrise Peak"],"Seongsan Ilchulbong","natural_attraction","Jeju"),
 ("jeju_seongsan","섭지코지",["섭지코지","Seopjikoji"],"Seopjikoji","natural_attraction","Jeju"),
 ("jeju_man_janggul","만장굴",["만장굴","Manjanggul Cave"],"Manjanggul Cave","natural_attraction","Jeju"),
 ("jeju_loveland","제주러브랜드",["제주러브랜드","Jeju Loveland"],"Jeju Loveland","tourist_facility","Jeju"),
 ("cheonjeyeon_falls","천제연폭포",["천제연폭포","Cheonjeyeon Falls"],"Cheonjeyeon Falls","natural_attraction","Jeju"),
 ("jeongbang_falls","정방폭포",["정방폭포","Jeongbang Falls"],"Jeongbang Falls","natural_attraction","Jeju"),
 ("oedolgae","외돌개",["외돌개","Oedolgae"],"Oedolgae","natural_attraction","Jeju"),
 ("u_do","우도",["우도","Udo Island","Udo"],"Udo Island Jeju","island","Jeju"),
 ("daereungwon","대릉원",["대릉원","Daereungwon"],"Daereungwon","heritage","Gyeongbuk"),
 ("gyeongju_namsan","경주 남산",["경주 남산","Gyeongju Namsan"],"Gyeongju Namsan","mountain","Gyeongbuk"),
 ("gimhae_gaya_theme_park","가야테마파크",["가야테마파크","Gaya Theme Park"],"Gaya Theme Park","tourist_facility","Gyeongnam"),
 ("namhae_german_village","남해독일마을",["남해독일마을","Namhae German Village"],"Namhae German Village","traditional_village","Gyeongnam"),
 ("geoje_hakdong_beach","학동몽돌해변",["학동몽돌해변","Hakdong Mongdol Beach"],"Hakdong Mongdol Beach","beach","Gyeongnam"),
 ("daegu_83_tower","83타워",["83타워","83 Tower","E-World 83 Tower"],"83 Tower Daegu","tower","Daegu"),
 ("daegu_ap_san","앞산공원",["앞산공원","Apsan Park"],"Apsan Park","park","Daegu"),
 ("gwangju_may_18","5·18민주광장",["5·18민주광장","May 18 Democracy Square"],"May 18 Democracy Square","square","Gwangju"),
 ("seoul_gwanghwamun_square","광화문광장",["광화문광장","Gwanghwamun Square"],"Gwanghwamun Square","square","Seoul"),
 ("seoul_lotte_world_tower","롯데월드타워",["롯데월드타워","Lotte World Tower"],"Lotte World Tower","tower","Seoul"),
 ("seoul_coex","코엑스",["코엑스","COEX Convention & Exhibition Center","COEX"],"COEX Seoul","modern_architecture","Seoul"),
 ("incheon_chinatown","인천차이나타운",["인천차이나타운","Incheon Chinatown"],"Incheon Chinatown","traditional_village","Incheon"),
 ("ganghwa_dolmen","강화 고인돌",["강화 고인돌","Ganghwa Dolmen"],"Ganghwa Dolmen","heritage","Incheon"),
 ("paju_imjingak","임진각",["임진각","Imjingak"],"Imjingak","tourist_facility","Gyeonggi"),
 ("yangpyeong_dumulmeori","두물머리",["두물머리","Dumulmeori"],"Dumulmeori","natural_attraction","Gyeonggi"),
 ("gimpo_aegibong","애기봉평화생태공원",["애기봉평화생태공원","Aegibong Peace Ecopark"],"Aegibong Peace Ecopark","park","Gyeonggi"),
 ("chuncheon_soyangan_skywalk","소양강스카이워크",["소양강스카이워크","Soyanggang Skywalk"],"Soyanggang Skywalk","tourist_facility","Gangwon"),
 ("wonju_sogeumsan","소금산출렁다리",["소금산출렁다리","Sogeumsan Suspension Bridge"],"Sogeumsan Suspension Bridge","bridge","Gangwon"),
 ("taebaeksan","태백산",["태백산","Taebaeksan","Taebaeksan National Park"],"Taebaeksan","mountain","Gangwon"),
 ("samcheok_haesindang","해신당공원",["해신당공원","Haesindang Park"],"Haesindang Park","park","Gangwon"),
 ("yeongju_buseoksa","부석사",["부석사","Buseoksa","Buseoksa Temple"],"Buseoksa Yeongju","temple","Gyeongbuk"),
 ("mungyeongsaejae","문경새재",["문경새재","Mungyeong Saejae"],"Mungyeong Saejae","natural_attraction","Gyeongbuk"),
 ("uljin_bulgyeongsa","불영사",["불영사","Bulgyeongsa"],"Bulgyeongsa Temple","temple","Gyeongbuk"),
 ("chungju_tangeumdae","탄금대",["탄금대","Tangeumdae"],"Tangeumdae","park","Chungbuk"),
 ("jecheon_cheongpung","청풍문화재단지",["청풍문화재단지","Cheongpung Cultural Heritage Complex"],"Cheongpung Cultural Heritage Complex","heritage","Chungbuk"),
 ("asan_oesam","외암민속마을",["외암민속마을","Oeam Folk Village"],"Oeam Folk Village","traditional_village","Chungnam"),
 ("seosan_haemieupseong","해미읍성",["해미읍성","Haemieupseong Fortress"],"Haemieupseong","fortress","Chungnam"),
 ("iksan_mireuksaji","익산 미륵사지",["익산 미륵사지","Mireuksaji"],"Mireuksaji","heritage","Jeonbuk"),
 ("namwon_gwanghallu","광한루원",["광한루원","Gwanghallu Garden"],"Gwanghallu Garden","garden","Jeonbuk"),
 ("mokpo_gatbawi","목포 갓바위",["목포 갓바위","Gatbawi Rock"],"Gatbawi Rock Mokpo","natural_attraction","Jeonnam"),
]

ROBUSTNESS = {
 "gyeongbokgung_generic": ("경복궁", None, ["경복궁", "Gyeongbokgung", "Gyeongbokgung Palace"], "Gyeongbokgung Palace"),
 "geunjeongjeon": ("근정전", "경복궁", ["근정전", "Geunjeongjeon", "Geunjeongjeon Hall", "경복궁", "Gyeongbokgung", "Gyeongbokgung Palace"], "Geunjeongjeon Gyeongbokgung"),
 "gyeonghoeru": ("경회루", "경복궁", ["경회루", "Gyeonghoeru", "Gyeonghoeru Pavilion", "경복궁", "Gyeongbokgung", "Gyeongbokgung Palace"], "Gyeonghoeru Gyeongbokgung"),
 "gwanghwamun": ("광화문", "경복궁", ["광화문", "Gwanghwamun", "Gwanghwamun Gate", "경복궁", "Gyeongbokgung", "Gyeongbokgung Palace"], "Gwanghwamun Gyeongbokgung"),
 "gyeongbokgung_other": ("경복궁 내부", "경복궁", ["경복궁", "Gyeongbokgung", "Gyeongbokgung Palace"], "Gyeongbokgung Palace buildings"),
}

def api(params):
    params.update(format="json", formatversion="2")
    req = Request(API + "?" + urlencode(params), headers={"User-Agent": AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=45) as r:
        time.sleep(DELAY)
        return json.load(r)

def clean(value):
    return re.sub(r"<[^>]+>", "", html.unescape(value or "")).strip()

def categories_for(page):
    return [item.get("title", "").removeprefix("Category:") for item in page.get("categories", [])]

def depicts_for(qid):
    """Best-effort structured-data P180 labels; API absence is deliberately harmless."""
    if not qid: return []
    try:
        entity=api({"action":"wbgetentities", "ids":qid, "props":"claims"}).get("entities",{}).get(qid,{})
        ids=[v["mainsnak"]["datavalue"]["value"]["id"] for v in entity.get("claims",{}).get("P180",[])
             if v.get("mainsnak",{}).get("datavalue",{}).get("type")=="wikibase-entityid"]
        if not ids: return []
        entities=api({"action":"wbgetentities", "ids":"|".join(ids[:30]), "props":"labels", "languages":"en|ko"}).get("entities",{})
        return [x.get("labels",{}).get("en",x.get("labels",{}).get("ko",{})).get("value","") for x in entities.values()]
    except Exception:
        return []

def category_candidates(category):
    data=api({"action":"query", "list":"categorymembers", "cmtitle":"Category:"+category, "cmtype":"file", "cmlimit":100})
    return [x["title"] for x in data.get("query",{}).get("categorymembers",[])]

def candidates(query=None, category=None):
    titles=category_candidates(category) if category else []
    if not titles and query:
        data = api({"action":"query", "list":"search", "srnamespace":6, "srlimit":40, "srsearch":query})
        titles = [x["title"] for x in data.get("query", {}).get("search", [])]
    for offset in range(0, len(titles), 20):
        batch = titles[offset:offset+20]
        info = api({"action":"query", "prop":"imageinfo|categories|pageprops", "titles":"|".join(batch), "iiprop":"url|size|mime|extmetadata", "iiurlwidth":1600, "cllimit":"max"})
        for page in info.get("query", {}).get("pages", []):
            if page.get("missing") or not page.get("imageinfo"): continue
            yield page["title"], page["imageinfo"][0], categories_for(page), depicts_for(page.get("pageprops",{}).get("wikibase_item"))

def record_for_title(title):
    info=api({"action":"query", "prop":"imageinfo|categories|pageprops", "titles":title,
              "iiprop":"url|size|mime|extmetadata", "iiurlwidth":1600, "cllimit":"max"})
    pages=info.get("query",{}).get("pages",[])
    if not pages or pages[0].get("missing") or not pages[0].get("imageinfo"): return None
    page=pages[0]
    return valid(page["title"],page["imageinfo"][0],categories_for(page),depicts_for(page.get("pageprops",{}).get("wikibase_item")))

def valid(title, info, categories=(), depicts=()):
    meta = info.get("extmetadata", {})
    mime, w, h = info.get("mime"), int(info.get("width") or 0), int(info.get("height") or 0)
    license_name = clean(meta.get("LicenseShortName", {}).get("value", ""))
    description = clean(meta.get("ImageDescription", {}).get("value", ""))
    lower = (title + " " + description).casefold()
    blocked = ("map", "logo", "diagram", "illustration", "drawing", "painting", "sketch", "poster", "document", "scan", "korean art")
    free_license = ("cc" in license_name.casefold() or "public domain" in license_name.casefold()
                    or license_name.casefold().startswith("pd") or "gfdl" in license_name.casefold())
    if mime not in ALLOWED or w < MIN_W or h < MIN_H or not free_license or any(x in lower for x in blocked): return None
    url = info.get("thumburl") or info.get("url")
    if not url: return None
    return {"title":title,"source_page_url":"https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
      "direct_image_url":url,"author":clean(meta.get("Artist",{}).get("value", "")),
      "license":license_name,
      "license_url":meta.get("LicenseUrl",{}).get("value", ""),"description":description,
      "width":w,"height":h,"mime_type":mime,"categories":list(categories),"depicts":list(depicts),
      "text_leak_risk": any(x in lower for x in ("sign", "text", "lettering"))}

def metadata_text(record):
    return " ".join([record.get("title",""),record.get("description",""),*record.get("categories",[]),*record.get("depicts",[])]).casefold()

def term_in(text, term):
    """Avoid treating the 'uk' in Gyeongbuk or 'cat' in Category as a match."""
    term=term.casefold()
    return bool(re.search(r"(?<![a-z0-9])"+re.escape(term)+r"(?![a-z0-9])", text)) if re.fullmatch(r"[a-z0-9 .-]+",term) else term in text

def assess_place(record, place):
    """Conservative metadata-only relevance classifier.  Never calls the benchmark API."""
    text=metadata_text(record)
    required=[x.casefold() for x in place.get("required_terms",[]) if x]
    forbidden=[x.casefold() for x in place.get("forbidden_terms",[])]
    if any(term_in(text,x) for x in FOREIGN_TERMS) or any(term_in(text,x) for x in forbidden):
        return "REJECT", "foreign or explicitly forbidden location/term"
    if not any(term_in(text,x) for x in required):
        return "REJECT", "no canonical place name/synonym in title, description, categories, or depicts"
    if any(term_in(text,x) for x in SUBJECT_TERMS):
        return "REJECT", "metadata identifies a non-landmark foreground subject"
    korea_terms=("korea", "south korea", "대한민국", place.get("region","").casefold())
    if any(x and term_in(text,x) for x in korea_terms):
        return "PASS", "canonical place evidence and Korean/regional confirmation"
    return "PASS", "canonical place evidence in Commons metadata (no conflicting location)"

def download(url, destination):
    req = Request(url, headers={"User-Agent": AGENT})
    with urlopen(req, timeout=90) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)
    if destination.stat().st_size < 1024: raise ValueError("download too small")
    return hashlib.sha256(destination.read_bytes()).hexdigest()

def write_csv(path, rows, fields):
    temporary=path.with_suffix(path.suffix+".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as f:
        # Commons API records use `title`, while the durable source schema uses
        # `file_title`. Preserve it before dropping unknown API metadata.
        w=csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            normalized=dict(row)
            if "file_title" in fields and not normalized.get("file_title") and normalized.get("title"):
                normalized["file_title"]=normalized["title"]
            normalized.pop("title", None)
            w.writerow(normalized)
        f.flush(); os.fsync(f.fileno())
    os.replace(temporary,path)

def atomic_json(path, value):
    temporary=path.with_suffix(path.suffix+".tmp")
    with temporary.open("w",encoding="utf-8") as f:
        json.dump(value,f,ensure_ascii=False,indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(temporary,path)

def record_replacements(base):
    path=base/"place_replacements.jsonl"
    existing={}
    if path.exists():
        existing={item.get("image_id"):item.get("replacement_place_id") for item in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)}
    with path.open("a",encoding="utf-8") as output:
        for index, original in enumerate(REPLACEMENTS, 1):
            indices=[i for i,(pid,*_) in enumerate(DIVERSITY,1) if pid==original]
            if not indices: continue
            image_id=f"DIV{indices[0]:03d}"
            if existing.get(image_id)==REPLACEMENTS[original][0]: continue
            output.write(json.dumps({"image_id":image_id,"original_place_id":original,"replacement_place_id":REPLACEMENTS[original][0],"reason":"No acceptable Wikimedia Commons image after repeated searches"},ensure_ascii=False)+"\n")

def write_manual_review_candidates(base, source):
    """Flag potentially secondary subjects for a human review; never alters scoring."""
    terms=("pagoda", "replica", "bus", "boat", "food", "starbucks", "museum", "tourist")
    lines=[]
    for row in source:
        text=" ".join(str(row.get(k,"")) for k in ("file_title","title","description","categories")).casefold()
        matched=[term for term in terms if term in text]
        if matched:
            lines.append(f"{row['image_id']}\t{row.get('file_title',row.get('title',''))}\tpossible secondary subject: {', '.join(matched)}")
    (base/"manual_review_candidates.txt").write_text("\n".join(lines)+("\n" if lines else ""),encoding="utf-8")

def audit_existing(kind):
    """Audit downloaded files using only their Commons metadata and fixed place rules."""
    base=ROOT/kind; progress_path=base/"collection_progress.json"
    if progress_path.exists(): progress=json.loads(progress_path.read_text(encoding="utf-8"))
    elif (base/"sources.csv").exists():
        progress={"manifest":list(csv.DictReader((base/"manifest.csv").open(encoding="utf-8-sig",newline=""))),
                  "sources":list(csv.DictReader((base/"sources.csv").open(encoding="utf-8-sig",newline="")))}
    else: raise ValueError(f"{kind}: no progress or sources to audit")
    # A previous audit may have moved REJECTs. Reconstruct them from its audit
    # log so a rule update can re-evaluate rather than silently losing a file.
    prior=base/"collection_audit.jsonl"
    if prior.exists():
        known={m["image_id"] for m in progress["manifest"]}
        for line in prior.read_text(encoding="utf-8").splitlines():
            event=json.loads(line)
            image_id=event["image_id"]
            # Never revive old rejected metadata if the active image slot exists.
            if event.get("verdict")!="REJECT" or image_id in known or list((base/"images").glob(image_id+".*")): continue
            matches=list((base/"rejected").glob(image_id+".*"))
            if not matches: continue
            progress["manifest"].append({"image_id":image_id,"image_path":"rejected/"+matches[0].name,"place_id":event["place_id"],"capture_type":"representative","note":""})
            progress["sources"].append({"image_id":image_id,"place_id":event["place_id"],"image_path":"rejected/"+matches[0].name,"file_title":event.get("file_title","")})
            known.add(image_id)
    places=build_places(kind); kept_m=[]; kept_s=[]; rejected=base/"rejected"; rejected.mkdir(exist_ok=True)
    # Metadata is authoritative only when both active path and SHA match.
    source_by_key={(s.get("image_id"),s.get("image_path"),s.get("sha256")):s for s in progress["sources"]}
    audit_path=base/"collection_audit.jsonl"; counts={"PASS":0,"REJECT":0,"REVIEW":0}
    with audit_path.open("w",encoding="utf-8") as log:
        for manifest in progress["manifest"]:
            file=base/manifest["image_path"]
            actual_sha=hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else ""
            old=source_by_key.get((manifest["image_id"],manifest["image_path"],actual_sha),{})
            if not file.is_file(): verdict, reason, rec="REJECT", "image file missing", None
            elif old.get("provenance") == "manual_user_provided":
                verdict, reason, rec="PASS", "manual_user_provided active file", old
            else:
                try: rec=record_for_title(old.get("file_title", "")); verdict,reason=assess_place(rec,places[manifest["place_id"]]) if rec else ("REJECT","Commons file metadata unavailable")
                except Exception as e: rec=None; verdict,reason="REVIEW",f"Commons audit lookup failed: {type(e).__name__}"
            counts[verdict]+=1
            event={"image_id":manifest["image_id"],"place_id":manifest["place_id"],"verdict":verdict,"reason":reason,"file_title":old.get("file_title","")}
            log.write(json.dumps(event,ensure_ascii=False)+"\n"); print(f"{manifest['image_id']} {verdict}: {reason}")
            if verdict=="REJECT":
                if file.is_file(): shutil.move(str(file),str(rejected/file.name))
                continue
            if file.parent == rejected:
                restored=base/"images"/file.name; restored.parent.mkdir(exist_ok=True)
                shutil.move(str(file),str(restored)); manifest["image_path"]="images/"+restored.name
                old["image_path"]=manifest["image_path"]
            if rec:
                rec.update({k:old[k] for k in ("image_id","place_id","image_path","sha256","file_title") if k in old})
                old=rec
            if file.is_file() and "sha256" not in old:
                old["sha256"]=hashlib.sha256(file.read_bytes()).hexdigest()
            old["audit_status"]=verdict
            old["audit_reason"]=reason
            kept_m.append(manifest); kept_s.append(old)
    atomic_json(progress_path,{"manifest":kept_m,"sources":kept_s})
    print("Audit totals: " + ", ".join(f"{k}={v}" for k,v in counts.items()))
    return counts

def build_places(kind):
    if kind == "diversity":
        source_rows=[REPLACEMENTS.get(i, (i,n,a,q,c,r)) for i,n,a,q,c,r in DIVERSITY]
        places={i:{"detail_name":n,"parent_name":None,"accepted_names":a,"commons_query":q,"category":c,"region":r,
                   "canonical_name_ko":n,"canonical_name_en":a[-1],"commons_queries":[q,n,q+" Korea",q+" South Korea"],
                   "required_terms":list(dict.fromkeys([q,*a])),"forbidden_terms":[]}
                for i,n,a,q,c,r in source_rows}
        # Ambiguous names and known difficult searches get place-specific, geographic queries.
        if "pohang_space_walk" in places: places["pohang_space_walk"].update(canonical_name_en="Pohang Space Walk", commons_queries=["Pohang Space Walk","스페이스워크 포항","Pohang Space Walk Korea"], required_terms=["pohang space walk","스페이스워크","pohang"])
        if "gunsan_railroad_village" in places: places["gunsan_railroad_village"].update(canonical_name_en="Gyeongam Railroad Village", commons_queries=["Gyeongam Railroad Village","경암동 철길마을","경암동철길마을","Gunsan railroad village","Gyeongam-dong Railway Village"], required_terms=["gyeongam","경암","gunsan railroad village","경암동 철길마을"])
        if "petite_france" in places: places["petite_france"]["forbidden_terms"]=["luxembourg", "berdorf"]
        if "taean_anmyeondo" in places: places["taean_anmyeondo"]["forbidden_terms"]=["buan"]
        for pid, terms in {
            "dokdo": ["boat", "police", "tourist", "navy", "defense drill", "military", "exhibition", "photograph exhibition", "press conference", "museum", "watchtower"], "taejongdae": ["bus"],
            "buyeo_baesanjeong": ["replica", "museum", "goransa", "goransa temple"], "damyang_juknokwon": ["pagoda"],
            "ulsan_grand_park": ["bus"], "gimpo_aegibong": ["starbucks"],
            "iksan_mireuksaji": ["museum"],
        }.items():
            if pid in places: places[pid]["forbidden_terms"] = terms
        if "windy_hill" in places: places["windy_hill"]["commons_queries"]=["Windy Hill Geoje","바람의 언덕 거제","Geoje Windy Hill"]
        for pid, category in {"gyeongbokgung":"Gyeongbokgung", "changdeokgung":"Changdeokgung", "jongmyo":"Jongmyo", "seoraksan":"Seoraksan", "bulguksa":"Bulguksa"}.items():
            if pid in places: places[pid]["commons_category"]=category
        return places
    return {i:{"detail_name":n,"parent_name":p,"accepted_names":a,"commons_query":q}
            for i,(n,p,a,q) in ROBUSTNESS.items()}

def collect(kind, max_new=None):
    base=ROOT/kind; images=base/"images"; images.mkdir(parents=True, exist_ok=True)
    places=build_places(kind)
    if kind == "diversity": record_replacements(base)
    (base/"places.json").write_text(json.dumps(places,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if kind == "diversity": (ROOT/"diversity_places.json").write_text(json.dumps(places,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    target=100; progress_path=base/"collection_progress.json"
    progress=json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {"manifest":[],"sources":[]}
    manifest=progress["manifest"]; source=progress["sources"]
    # A progress entry is usable only when its named, hash-verified file is still present.
    manifest=[r for r in manifest if (base/r["image_path"]).is_file()]
    source=[r for r in source if any(m["image_id"]==r["image_id"] for m in manifest)]
    paths={m["image_id"]:base/m["image_path"] for m in manifest}
    for record in source:
        if not record.get("sha256"):
            record["sha256"]=hashlib.sha256(paths[record["image_id"]].read_bytes()).hexdigest()
    used_titles={r["file_title"] for r in source}; used_sha={r["sha256"] for r in source}
    items=list(places.items()) if kind=="diversity" else [(None,None)]*target
    added = 0
    for index, pair in enumerate(items, 1):
        pid, place = pair if kind=="diversity" else (list(places)[(index-1)%len(places)], places[list(places)[(index-1)%len(places)]])
        image_id=("DIV" if kind=="diversity" else "ROB")+f"{index:03d}"
        if any(r["image_id"] == image_id for r in manifest):
            continue
        query=place["commons_query"]
        # query variants diversify the robustness pool without interpreting model results.
        if kind=="gyeongbokgung": query += ["", " exterior", " night", " tourists", " panorama"][((index-1)//5)%5]
        chosen=None
        try:
            query_plan=[]
            if place.get("commons_category"): query_plan.append((None,place["commons_category"]))
            query_plan += [(q,None) for q in place.get("commons_queries",[query])]
            for search_query, category in query_plan:
                for title, info, categories, depicts in candidates(search_query, category):
                    record=valid(title,info,categories,depicts)
                    verdict, _ = assess_place(record,place) if record else ("REJECT", "invalid media")
                    if record and verdict == "PASS" and title not in used_titles:
                        ext=ALLOWED[record["mime_type"]]; temp=images/(image_id+ext+".part")
                        try: sha=download(record["direct_image_url"],temp)
                        except Exception: temp.unlink(missing_ok=True); continue
                        if sha in used_sha: temp.unlink(missing_ok=True); continue
                        final=images/(image_id+ext); temp.replace(final); record["sha256"]=sha; record["file_title"]=title
                        chosen=(final,record); break
                if chosen: break
        except Exception as e:
            print(f"{image_id}: API/query failure: {e}", file=sys.stderr)
        if not chosen:
            failure={"image_id":image_id,"place_id":pid,"queries":place.get("commons_queries",[query]),"reason":"no candidate passed conservative Commons metadata audit"}
            with (base/"collection_failures.jsonl").open("a",encoding="utf-8") as out: out.write(json.dumps(failure,ensure_ascii=False)+"\n")
            print(f"{image_id}: FAILED (recorded; continuing)", file=sys.stderr)
            continue
        final, rec=chosen; used_titles.add(rec["file_title"]); used_sha.add(rec["sha256"])
        rec["audit_status"]="PASS"; rec["audit_reason"]="candidate passed metadata relevance rules"
        capture = "representative" if kind=="diversity" else ["general","detail","night","tourists","distant"][((index-1)//5)%5]
        manifest.append({"image_id":image_id,"image_path":"images/"+final.name,"place_id":pid,"capture_type":capture,"note":""})
        rec.update(image_id=image_id,place_id=pid,image_path="images/"+final.name); source.append(rec)
        progress_path.write_text(json.dumps({"manifest":manifest,"sources":source},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"{image_id}: {rec['file_title']}", flush=True)
        added += 1
        if max_new and added >= max_new:
            print(f"Checkpointed {added} new images; rerun to continue.")
            return
    write_csv(base/"manifest.csv",manifest,["image_id","image_path","place_id","capture_type","note"])
    write_csv(base/"sources.csv",source,["image_id","place_id","image_path","file_title","source_page_url","direct_image_url","author","license","license_url","description","categories","depicts","width","height","mime_type","sha256","text_leak_risk","audit_status","audit_reason"])
    if len(manifest) != target:
        print(f"{kind}: {target-len(manifest)} place(s) failed; dataset_lock.json was not created.", file=sys.stderr)
        return
    failure_path=base/"collection_failures.jsonl"
    present={x["image_id"] for x in manifest}
    active_failures=[] if not failure_path.exists() else [json.loads(line) for line in failure_path.read_text(encoding="utf-8").splitlines() if line and json.loads(line).get("image_id") not in present]
    if any(x.get("audit_status") != "PASS" for x in source) or active_failures:
        print(f"{kind}: non-PASS audit state or unresolved collection failures; dataset_lock.json was not created.", file=sys.stderr)
        return
    write_manual_review_candidates(base, source)
    lock={"benchmark":kind,"image_count":len(manifest),"sha256":{x["image_id"]:x["sha256"] for x in source},"places_sha256":hashlib.sha256((base/"places.json").read_bytes()).hexdigest(),"audit_status_counts":{"PASS":100,"REVIEW":0,"REJECT":0},"active_collection_failures":0}
    (base/"dataset_lock.json").write_text(json.dumps(lock,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    progress_path.unlink(missing_ok=True)

def reject_images(kind, image_ids):
    """Move human-rejected files aside and restore a resumable checkpoint."""
    base=ROOT/kind
    manifest=list(csv.DictReader((base/"manifest.csv").open(encoding="utf-8-sig",newline="")))
    sources=list(csv.DictReader((base/"sources.csv").open(encoding="utf-8-sig",newline="")))
    by_source={row["image_id"]:row for row in sources}; rejected=base/"rejected"; rejected.mkdir(exist_ok=True)
    retained_m=[]; retained_s=[]
    log=base/"manual_rejections.jsonl"
    with log.open("a",encoding="utf-8") as output:
        for row in manifest:
            if row["image_id"] not in image_ids:
                retained_m.append(row); retained_s.append(by_source[row["image_id"]]); continue
            image=base/row["image_path"]
            destination=rejected/(image.stem+"_manual_reject"+image.suffix)
            number=2
            while destination.exists():
                destination=rejected/(image.stem+f"_manual_reject_{number}"+image.suffix); number+=1
            if image.is_file(): shutil.move(str(image),str(destination))
            output.write(json.dumps({"image_id":row["image_id"],"place_id":row["place_id"],"old_file":image.name,"rejected_file":destination.name,"reason":"human manual review rejection"},ensure_ascii=False)+"\n")
    (base/"collection_progress.json").write_text(json.dumps({"manifest":retained_m,"sources":retained_s},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (base/"dataset_lock.json").unlink(missing_ok=True)
    print(f"Moved {len(image_ids)} manual rejects to {rejected}")

def recover_known_active(kind):
    """Recover the latest locally-present replacements; metadata lookup only, no downloads."""
    if kind != "diversity": raise ValueError("only diversity recovery is supported")
    base=ROOT/kind; places=build_places(kind)
    titles={
        "DIV046":"File:Baekhwajeon Pavilion.jpg",
        "DIV056":"File:Bamboo forest in Damyang South Korea 2015-05-06(1).jpg",
        "DIV060":None,
        "DIV086":"File:20240927 애기봉 포토워크 Real rism 03.jpg",
        "DIV098":"File:Mireuksaji Stone Pagoda 20190505.png",
    }
    progress=json.loads((base/"collection_progress.json").read_text(encoding="utf-8"))
    manifest={r["image_id"]:r for r in progress["manifest"]}; sources={r["image_id"]:r for r in progress["sources"]}
    for image_id,title in titles.items():
        candidates=list((base/"images").glob(image_id+".*")) or list((base/"rejected").glob(image_id+".*"))
        if not candidates: raise ValueError(f"{image_id}: latest local replacement file is missing")
        file=max(candidates,key=lambda p:p.stat().st_mtime_ns)
        record=record_for_title(title) if title else {"file_title":"manual_user_provided","source_page_url":"manual_user_provided","direct_image_url":"manual_user_provided","author":"manual_user_provided","license":"manual_user_provided","license_url":"","description":"User-provided replacement; manually reviewed.","categories":[],"depicts":[],"width":"","height":"","mime_type":"image/jpeg","text_leak_risk":False,"provenance":"manual_user_provided"}
        if not record: raise ValueError(f"{image_id}: Commons metadata unavailable for {title}")
        destination=base/"images"/(image_id+file.suffix.lower())
        if file.resolve()!=destination.resolve():
            if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()!=hashlib.sha256(file.read_bytes()).hexdigest():
                raise ValueError(f"{image_id}: conflicting active image")
            if not destination.exists(): shutil.move(str(file),str(destination))
        place_id=list(places)[int(image_id[3:])-1]
        digest=hashlib.sha256(destination.read_bytes()).hexdigest()
        record.update(image_id=image_id,place_id=place_id,image_path="images/"+destination.name,file_title=title,sha256=digest,audit_status="PASS",audit_reason="recovered current local replacement by path and SHA256")
        manifest[image_id]={"image_id":image_id,"image_path":record["image_path"],"place_id":place_id,"capture_type":"representative","note":""}
        sources[image_id]=record
    ordered=[f"DIV{i:03d}" for i in range(1,101)]
    if set(manifest)!=set(ordered) or set(sources)!=set(ordered): raise ValueError("recovery did not yield exactly DIV001-DIV100")
    atomic_json(base/"collection_progress.json",{"manifest":[manifest[i] for i in ordered],"sources":[sources[i] for i in ordered]})

def main():
    p=argparse.ArgumentParser(); p.add_argument("--all",action="store_true"); p.add_argument("--benchmark",choices=["diversity","gyeongbokgung"]); p.add_argument("--max-new",type=int); p.add_argument("--write-place-definitions",action="store_true"); p.add_argument("--audit-existing",action="store_true",help="Audit current Commons files; move only REJECT files to rejected/"); p.add_argument("--reject-image-ids",nargs="+",help="Human-reviewed IDs to replace without changing their places"); p.add_argument("--recover-known-active",action="store_true"); a=p.parse_args()
    if not a.all and not a.benchmark: p.error("use --all or --benchmark")
    if a.max_new is not None and a.max_new < 1: p.error("--max-new must be positive")
    kinds=["diversity","gyeongbokgung"] if a.all else [a.benchmark]
    if a.write_place_definitions:
        for kind in kinds:
            base=ROOT/kind; (base/"images").mkdir(parents=True,exist_ok=True)
            text=json.dumps(build_places(kind),ensure_ascii=False,indent=2)+"\n"
            (base/"places.json").write_text(text,encoding="utf-8")
            if kind=="diversity": (ROOT/"diversity_places.json").write_text(text,encoding="utf-8")
        return
    if a.audit_existing:
        for kind in kinds: audit_existing(kind)
        return
    if a.reject_image_ids:
        if len(kinds) != 1: p.error("--reject-image-ids requires one --benchmark")
        reject_images(kinds[0],set(a.reject_image_ids))
        return
    if a.recover_known_active:
        if len(kinds) != 1: p.error("--recover-known-active requires one --benchmark")
        recover_known_active(kinds[0]); return
    for kind in kinds: collect(kind,a.max_new)
if __name__ == "__main__": main()
