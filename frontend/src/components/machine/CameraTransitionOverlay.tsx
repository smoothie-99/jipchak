interface CameraTransitionOverlayProps {
  isTransitioning: boolean;
}

const CameraTransitionOverlay = ({ isTransitioning }: CameraTransitionOverlayProps) => {
  return (
    <div 
      className={`absolute inset-0 z-toast bg-black/90 backdrop-blur-sm flex items-center justify-center transition-opacity duration-200 pointer-events-none ${
        isTransitioning ? 'opacity-100' : 'opacity-0'
      }`}
    >
      <span className="text-white font-crayon text-[clamp(24px,4vw,40px)] tracking-widest">
        카메라 전환 중...
      </span>
    </div>
  );
};

export default CameraTransitionOverlay;
