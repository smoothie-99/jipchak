import time
import numpy as np
import argparse

# --- 프로젝트 의존성 ---
# three_jaw_grasp 패키지의 주요 컴포넌트들을 import 합니다.
# 실제 프로젝트 구조에 맞게 경로를 조정해야 할 수 있습니다.
from three_jaw_grasp import (
    GraspPipeline,
    FeatureExtractor,
    GraspDataLogger,
    ThreeJawEvaluator,
    ModelFactory,
    AdapterFactory,
    EvaluatorFactory,
)
# --- 실제 하드웨어 연동을 위한 (가상) 모듈 ---
# from your_project.robot import RobotController
# from your_project.camera import Camera

class RobotController:
    """실제 집게를 제어하는 클래스 (구현 필요)"""
    def __init__(self):
        print("[Gripper] 집게 컨트롤러가 초기화되었습니다. (가상)")
        # 예: 시리얼 포트 연결, ROS 노드 초기화 등

    def move_and_grasp(self, grasp: 'GraspCandidate'):
        """예측된 파지 정보로 집게를 움직여 파지를 수행합니다."""
        print(f"[Gripper] 좌표 (x={grasp.center_x:.1f}, y={grasp.center_y:.1f}, z={grasp.center_z:.3f})로 이동하여 파지를 수행합니다.")
        print(f"[Gripper] 폭: {grasp.width:.3f}m, 각도: {np.degrees(grasp.angle):.1f}도")
        # TODO: 실제 집게 제어 로직 (e.g., 시리얼 통신, ROS 메시지 전송 등)
        time.sleep(2) # 집게가 실제로 움직이는 시간만큼 대기
        print("[Gripper] 파지 동작 완료.")

class Camera:
    """실제 카메라에서 RGB, Depth 이미지를 가져오는 클래스 (구현 필요)"""
    def __init__(self, device_id=0):
        # self.cap = cv2.VideoCapture(device_id) # 실제 웹캠 사용 시
        # if not self.cap.isOpened():
        #    raise IOError(f"Cannot open camera {device_id}")
        print("[Camera] 카메라가 초기화되었습니다. (가상)")

    def get_frames(self):
        """카메라에서 프레임을 가져옵니다."""
        print("\n[Camera] 프레임 캡처 시도... (현재는 가상 이미지 생성)")
        # ret, rgb_frame = self.cap.read() # 실제 웹캠 사용 시
        # depth_frame = ... # 실제 Depth 카메라 SDK에서 가져오기
        rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        depth = np.random.rand(480, 640).astype(np.float32)
        return rgb, depth

    def release(self):
        # self.cap.release() # 실제 웹캠 사용 시
        pass

def main(args):
    """
    터미널 입력(y/n)을 사용하여 파지 성공/실패 데이터를 수집하는
    상호작용형 테스트 스크립트.
    """
    # 1. 파이프라인 및 로거 초기화
    print(f"[Setup] 모델 로딩: {args.model_type} (가중치: {args.weights})")
    grasp_model = ModelFactory.create(args.model_type, weights_path=args.weights)
    adapter = AdapterFactory.create(args.model_type)
    
    # 학습된 평가 모델을 사용할지, 규칙 기반 평가 모델을 사용할지 결정
    if args.evaluator_model:
        print(f"[Setup] 학습된 평가 모델 로딩: {args.evaluator_model}")
        evaluator = ThreeJawEvaluator(
            config_path=args.config,
            model_path=args.evaluator_model
        )
    else:
        print(f"[Setup] 규칙 기반 평가 모델 사용: {args.evaluator_type}")
        evaluator = EvaluatorFactory.create(
            args.evaluator_type, 
            config_path=args.config
        )
    # detector = SSDLiteDetector() # 객체 탐지기(YOLO 등)를 파이프라인에 추가할 경우 주석 해제

    pipeline = GraspPipeline(
        model=grasp_model,
        adapter=adapter,
        evaluator=evaluator,
        # detector=detector,
    )

    feature_extractor = FeatureExtractor()
    logger = GraspDataLogger(args.log_file, feature_extractor)

    # 1.1 실제 하드웨어 초기화
    robot = RobotController()
    camera = Camera()

    print("="*50)
    print("데이터 수집을 시작합니다.")
    print("파지 시도 후, 터미널에 결과를 입력하고 Enter를 누르세요.")
    print("  - 'y': 파지 성공 (Yes)")
    print("  - 'n': 파지 실패 (No)")
    print("  - 'q': 프로그램 종료 (Quit)")
    print("="*50)

    try:
        while True:
            # 2. 카메라로부터 RGB, Depth 이미지 프레임 받아오기
            # 이 부분은 실제 카메라 SDK 또는 이미지 파일 로딩 코드로 대체되어야 합니다.
            rgb, depth = camera.get_frames()

            try:
                # 3. 최적 파지점 예측 및 집게 제어
                best_grasp = pipeline.predict_best(rgb, depth)
                print(f"[AI] 최적 파지점 예측: (x={best_grasp.center_x:.1f}, y={best_grasp.center_y:.1f}, width={best_grasp.width:.2f})")
                robot.move_and_grasp(best_grasp)

                # 4. 사용자로부터 성공/실패 피드백 받기
                should_quit = False
                while True:
                    feedback = input("파지에 성공했나요? (y: 성공 / n: 실패 / q: 종료): ").lower().strip()
                    if feedback == 'y':
                        logger.log_attempt(best_grasp, depth, success=True)
                        print("[Log] '성공'으로 기록되었습니다.")
                        break
                    elif feedback == 'n':
                        logger.log_attempt(best_grasp, depth, success=False)
                        print("[Log] '실패'로 기록되었습니다.")
                        break
                    elif feedback == 'q':
                        print("프로그램을 종료합니다.")
                        should_quit = True
                        break
                    else:
                        print("y, n, q 중 하나를 입력해주세요.")
                
                if should_quit:
                        break

            except ValueError as e:
                print(f"파지 후보를 찾지 못했습니다: {e}. 5초 후 재시도합니다.")
                time.sleep(5)

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        camera.release()
        print("데이터 수집이 완료되었습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="파지 데이터 수집 상호작용 스크립트")
    parser.add_argument("--model-type", type=str, default="yolo_seg", help="사용할 파지 모델 타입 (Factory 등록 이름)")
    parser.add_argument("--weights", type=str, default="trained-models/best_v3.pt", help="파지 모델 가중치 파일 경로")
    parser.add_argument("--config", type=str, default="config/gripper_spec.yaml", help="집게 사양 설정 파일 경로")
    parser.add_argument("--log-file", type=str, default="grasp_log.jsonl", help="성공/실패 로그를 저장할 파일")
    
    # 평가기 선택 옵션 추가
    parser.add_argument("--evaluator-type", type=str, default="chick", choices=["default", "chick"], help="사용할 규칙 기반 평가기 타입")
    parser.add_argument("--evaluator-model", type=str, default=None, help="사용할 학습된 평가 모델(.pth) 경로. 지정 시 규칙 기반 평가기 대신 사용됩니다.")

    args = parser.parse_args()
    main(args)
