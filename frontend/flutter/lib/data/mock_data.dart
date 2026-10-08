import '../models/place.dart';
import '../models/travel_notification.dart';

/// 서버 API가 연결되기 전 화면을 구성하는 예시 장소·알림 데이터입니다.
const savedPlaces = <Place>[
  Place(
    id: 'p1',
    name: '안목해변',
    region: '강원 강릉시',
    tags: ['바다', '카페', '산책'],
    image: 'photo-1507525428034-b723cf961d3e',
  ),
  Place(
    id: 'p2',
    name: '황리단길',
    region: '경북 경주시',
    tags: ['맛집', '전통', '카페'],
    image: 'photo-1569383746724-6f1b882b8f46',
  ),
  Place(
    id: 'p3',
    name: '애월 해안도로',
    region: '제주 제주시',
    tags: ['바다', '드라이브', '휴식'],
    image: 'photo-1537996194471-e657df975ab4',
  ),
  Place(
    id: 'p4',
    name: '광안리해수욕장',
    region: '부산 수영구',
    tags: ['바다', '야경', '맛집'],
    image: 'photo-1517404215738-15263e9f9178',
  ),
  Place(
    id: 'p5',
    name: '전주 한옥마을',
    region: '전북 전주시',
    tags: ['전통문화', '맛집', '체험'],
    image: 'assets/images/jeonju-hanok.jpg',
  ),
  Place(
    id: 'p6',
    name: '남이섬',
    region: '강원 춘천시',
    tags: ['자연', '산책', '체험'],
    image: 'photo-1464822759023-fed622ff2c3b',
  ),
];
const notifications = <TravelNotification>[
  TravelNotification('✈️', '여행 D-5', '강릉 여행이 5일 남았어요.', '방금', unread: true),
  TravelNotification(
    '🌧',
    '오늘 비 예보',
    '강수확률이 높아요. 비 오는 날 일정을 확인해보세요.',
    '방금',
    unread: true,
  ),
];
