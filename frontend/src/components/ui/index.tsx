import { cloneElement, isValidElement, useEffect, useId, useRef } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, CircleHelp, X } from "lucide-react";
export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button className={`button ${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}
export function LinkButton({
  to,
  children,
  variant = "primary",
  className = "",
}: {
  to: string;
  children: ReactNode;
  variant?: string;
  className?: string;
}) {
  return (
    <Link to={to} className={`button ${variant} ${className}`}>
      {children}
    </Link>
  );
}
export function Badge({
  children,
  tone = "green",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function PageHeader({
  title,
  description,
  back,
  action,
}: {
  title: string;
  description?: string;
  back?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      {back && (
        <Link className="back-link" to={back}>
          <ArrowLeft size={16} />
          Quay lại
        </Link>
      )}
      <div className="heading-row">
        <div>
          <h1 tabIndex={-1}>{title}</h1>
          {description && <p>{description}</p>}
        </div>
        {action}
      </div>
    </header>
  );
}
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <CircleHelp size={32} />
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <div
      className={`notice ${tone}`}
      role={tone === "error" ? "alert" : undefined}
    >
      {children}
    </div>
  );
}
export function Field({
  label,
  hint,
  error,
  children,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
  children?: ReactNode;
}) {
  const generated = useId();
  const child = isValidElement<{
    id?: string;
    "aria-describedby"?: string;
    "aria-invalid"?: boolean;
  }>(children)
    ? children
    : null;
  const id = props.id ?? child?.props.id ?? generated;
  const helpId = hint || error ? `${id}-help` : undefined;
  const control = child
    ? cloneElement(child, {
        id,
        "aria-describedby":
          [child.props["aria-describedby"], helpId].filter(Boolean).join(" ") ||
          undefined,
        "aria-invalid": error ? true : child.props["aria-invalid"],
      })
    : children;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {control ?? (
        <input
          {...props}
          id={id}
          aria-invalid={!!error}
          aria-describedby={helpId}
        />
      )}{" "}
      {(hint || error) && (
        <small id={`${id}-help`} className={error ? "error-text" : ""}>
          {error || hint}
        </small>
      )}
    </div>
  );
}
export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const previous = document.activeElement as HTMLElement;
    if (!dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="dialog-content">
        <div className="heading-row">
          <h2 id={titleId}>{title}</h2>
          <Button variant="ghost" aria-label="Đóng" onClick={onClose}>
            <X size={20} />
          </Button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
export function Skeleton() {
  return (
    <div className="skeleton" role="status" aria-label="Đang tải dữ liệu mẫu">
      <span />
      <span />
      <span />
    </div>
  );
}
export function SectionHeading({
  title,
  to,
  label = "Xem tất cả",
}: {
  title: string;
  to?: string;
  label?: string;
}) {
  return (
    <div className="section-heading">
      <h2>{title}</h2>
      {to && (
        <Link to={to}>
          {label}
          <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}
export function Progress({ value, max }: { value: number; max: number }) {
  return (
    <div
      className="progress"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max || 1}
      aria-label={`${value}/${max} bước đã làm`}
    >
      <span style={{ width: `${max ? (value / max) * 100 : 0}%` }} />
    </div>
  );
}
export function CheckMark() {
  return <Check size={18} />;
}
