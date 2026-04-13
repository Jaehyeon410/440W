import { cn } from "../components/ui/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant: "cook-now" | "needs-sub" | "similar" | "different";
}

export function Badge({ children, variant }: BadgeProps) {
  const variantStyles = {
    "cook-now": "bg-green-100 text-green-800 border-green-300",
    "needs-sub": "bg-orange-100 text-orange-800 border-orange-300",
    "similar": "bg-blue-100 text-blue-800 border-blue-300",
    "different": "bg-purple-100 text-purple-800 border-purple-300",
  };

  return (
    <span
      className={cn(
        "px-3 py-1 rounded-full border text-xs font-medium",
        variantStyles[variant]
      )}
    >
      {children}
    </span>
  );
}