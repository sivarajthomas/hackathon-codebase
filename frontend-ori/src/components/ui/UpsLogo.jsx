// Official UPS shield logo image, served from /public.
export default function UpsLogo({ className = '' }) {
  return (
    <img
      src="/ups-logo.png"
      alt="UPS"
      className={`object-contain ${className}`}
      draggable={false}
    />
  )
}
