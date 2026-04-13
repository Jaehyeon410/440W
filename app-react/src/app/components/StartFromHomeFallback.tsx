import { useNavigate } from "react-router";

interface StartFromHomeFallbackProps {
  title: string;
}

export function StartFromHomeFallback({ title }: StartFromHomeFallbackProps) {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center bg-white border rounded-xl p-8 max-w-md w-full mx-4">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">{title}</h2>
        <p className="text-gray-600 mb-6">Please start from Home.</p>
        <button
          onClick={() => navigate("/")}
          className="px-6 py-2.5 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors"
        >
          Go to Home
        </button>
      </div>
    </div>
  );
}
