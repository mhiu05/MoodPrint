import { Link } from "react-router-dom";
export function Brand({ to = "/home" }: { to?: string }) {
  return (
    <Link to={to} className="brand" aria-label="SafeVoice — trang chủ">
      <span className="brand-mark">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M7 4.5h9a4 4 0 0 1 4 4v6a4 4 0 0 1-4 4h-5l-5 3v-3a4 4 0 0 1-3-4v-6a4 4 0 0 1 4-4Z"
            stroke="currentColor"
            strokeWidth="1.7"
          />
          <path
            d="m8 10 3 4 5-6"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      SafeVoice
    </Link>
  );
}
export function FlowerArt() {
  return (
    <div className="hero-art" aria-hidden="true">
      <i className="petal" />
      <i className="petal" />
      <i className="petal" />
      <i className="petal" />
      <i className="petal" />
      <span className="flower-center">
        <svg width="42" height="42" viewBox="0 0 40 40" fill="none">
          <path
            d="M11 21c4 7 14 7 18 0M12 15h.1M28 15h.1"
            stroke="#477656"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
        </svg>
      </span>
    </div>
  );
}
