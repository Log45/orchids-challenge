'use client';

import { useState } from "react";

function ClonedWebsite({ dir }: { dir: string }) {
  if (!dir) return null;
  const dirWithoutPrefix = dir.replace('cloned_site/', '');
  const src = `http://localhost:8000/static/${dirWithoutPrefix}/index.html`;
  return (
    <div className="w-full h-[calc(100vh-200px)] border rounded shadow">
      <iframe
        src={src}
        title="Cloned Website"
        sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads allow-modals"
        className="w-full h-full bg-white"
        referrerPolicy="no-referrer"
      />
    </div>
  );
}

export default function Home() {
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [clonedDir, setClonedDir] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch("http://localhost:8000/websites", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url: url,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to submit URL");
      }

      const data = await response.json();
      console.log("Success:", data);
      setClonedDir(data.original_dir);
      setUrl(""); // Clear the input after successful submission
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      <div className="w-full max-w-4xl mx-auto p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
           Orchids Take-home Website Cloner
          </h1>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Enter a website URL to get started
          </p>
        </div>
        
        <form className="mb-8" onSubmit={handleSubmit}>
          <div className="flex gap-4">
            <input
              id="url"
              name="url"
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="flex-1 rounded-md border-0 py-3 px-4 text-gray-900 dark:text-white ring-1 ring-inset ring-gray-300 dark:ring-gray-700 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue-600 dark:focus:ring-blue-500 bg-white dark:bg-gray-800"
              placeholder="https://www.orchids.app/"
            />
            <button
              type="submit"
              disabled={isLoading}
              className={`px-6 py-3 rounded-md text-sm font-semibold text-white transition-colors ${
                isLoading 
                  ? "bg-blue-400 cursor-not-allowed" 
                  : "bg-blue-600 hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              }`}
            >
              {isLoading ? "Submitting..." : "Submit"}
            </button>
          </div>

          {error && (
            <div className="text-red-500 text-sm text-center mt-2">
              {error}
            </div>
          )}
        </form>

        <ClonedWebsite dir={clonedDir} />
      </div>
    </div>
  );
}
