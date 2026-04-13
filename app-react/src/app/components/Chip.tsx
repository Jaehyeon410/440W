import { cn } from "../components/ui/utils";

interface ChipProps {
  children: React.ReactNode;
  selected?: boolean;
  onClick?: () => void;
  variant?: "default" | "success" | "warning";
}

export function Chip({ children, selected = false, onClick, variant = "default" }: ChipProps) {
  const variantStyles = {
    default: selected 
      ? "bg-blue-600 text-white border-blue-600" 
      : "bg-white text-gray-700 border-gray-300 hover:border-blue-500",
    success: "bg-green-100 text-green-800 border-green-300",
    warning: "bg-orange-100 text-orange-800 border-orange-300",
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "px-4 py-2 rounded-full border text-sm transition-colors",
        variantStyles[variant],
        onClick && "cursor-pointer"
      )}
    >
      {children}
    </button>
  );
}