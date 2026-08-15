import { ReactNode } from 'react';

/**
 * GuideSlides
 * 사용 가이드 모달의 슬라이드 정보를 정의합니다.
 */
export interface GuideSlide {
  step: string;
  title: string;
  description: ReactNode;
}

export const guideSlides: GuideSlide[] = [
  {
    step: '1',
    title: '조작방법',
    description: (
      <>
        <span className="font-black text-blue-500">파란</span> 버튼 누르면 뽑기 시작
        <br></br>
        <span className="font-black text-red-500">빨간</span> 버튼 누르면 집게 하강
        <br></br>
        <span className="font-black text-green-500">조이스틱</span>으로 집게 위치 이동
      </>
    ),
  },
  {
    step: '2',
    title: '메인 페이지',
    description: (
      <>
        <span className="font-black text-yellow-600">Start</span> 클릭 시 플레이 페이지로
        <br></br>
        <span className="font-black text-yellow-600">Guide</span> 클릭 시 사용법 제공
      </>
    ),
  },
  {
    step: '3',
    title: '플레이 페이지',
    description: (
      <>
        실시간 영상, <span className="font-black text-green-500">집기 확률</span>,
        <br></br>
        나의 기록 확인
        <br></br>
        <span className="font-black text-red-500">서브 카메라</span> 클릭 시
        <br></br>
        <span className="font-black text-blue-500">메인 카메라</span>와 위치 변경
        <br></br>
        <span className="font-black text-yellow-600">설정</span> 클릭 시 소리 설정
      </>
    ),
  },
  {
    step: '4',
    title: '소리 설정',
    description: (
      <>
        배경음, 효과음, 안내음
        <br></br>
        크기 조절
      </>
    ),
  },
  {
    step: '5',
    title: '뽑기 완료',
    description: (
      <>
        선택한 수만큼 플레이하면
        <br></br>
        다운로드 할지 선택
        <br></br>
        <span className="font-black text-red-500">30초</span> 동안 미선택 시 자동 종료
      </>
    ),
  },
  {
    step: '6',
    title: 'QR 코드 생성',
    description: (
      <>
        <span className="font-black text-yellow-600">다운로드</span> 선택 시
        <br></br>
        <span className="font-black text-yellow-600">QR 코드</span> 생성
        <br></br>
        카메라 스캔 시
        <br></br>
        <span className="font-black text-yellow-600">다운로드 링크</span> 제공
        <br></br>
        <span className="font-black text-red-500">1분</span> 동안만 활성화
      </>
    ),
  },
  {
    step: '7',
    title: '다운로드',
    description: (
      <>
        선택한 수만큼
        <br></br>
        스트리밍 및 저장
        <br></br>
        <span className="font-black text-red-500">30분</span> 후 세션 종료
      </>
    ),
  },
];
