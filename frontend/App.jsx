import React, { useEffect, useRef, useState } from 'react';

// --- Icons ---
const ChevronDown = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m6 9 6 6 6-6" />
  </svg>
);

const UpArrow = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="m5 12 7-7 7 7" /><path d="M12 19V5" />
  </svg>
);

const StarIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
);

const SparkleIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
  </svg>
);


const VoiceIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" x2="12" y1="19" y2="22" />
  </svg>
);


const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const formatStatus = (status) => {
  if (!status) return 'Idle';
  const normalized = String(status).toLowerCase();
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
};

// --- Components ---

const VideoBackground = () => {
  const videoRef = useRef(null);
  const opacityRef = useRef(0);
  const animFrameRef = useRef(null);
  const fadingOutRef = useRef(false);

  // Custom JS requestAnimationFrame fade system (no CSS transitions)
  const fade = (targetOpacity, duration) => {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    const startOpacity = opacityRef.current;
    const startTime = performance.now();

    const animate = (time) => {
      const elapsed = time - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const currentOpacity = startOpacity + (targetOpacity - startOpacity) * progress;

      opacityRef.current = currentOpacity;
      if (videoRef.current) {
        videoRef.current.style.opacity = currentOpacity;
      }

      if (progress < 1) {
        animFrameRef.current = requestAnimationFrame(animate);
      }
    };

    animFrameRef.current = requestAnimationFrame(animate);
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video) return;

    // Trigger fade out 0.55s before the end
    if (video.duration - video.currentTime <= 0.55 && !fadingOutRef.current) {
      fadingOutRef.current = true;
      fade(0, 250);
    }
  };

  const handleEnded = () => {
    const video = videoRef.current;
    if (!video) return;

    // Hard reset opacity to 0 just in case frame dropped
    video.style.opacity = 0;
    opacityRef.current = 0;

    setTimeout(() => {
      video.currentTime = 0;
      fadingOutRef.current = false;
      video.play().catch((e) => console.error('Playback failed', e));
      fade(1, 250);
    }, 100);
  };

  const handleLoadedData = () => {
    fadingOutRef.current = false;
    fade(1, 250);
  };

  useEffect(() => {
    const video = videoRef.current;
    // Catch cases where loadeddata fired before hydration
    if (video && video.readyState >= 3) {
      handleLoadedData();
    }

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  return (
    <div className="absolute inset-0 z-0 bg-black overflow-hidden pointer-events-none">
      <video
        ref={videoRef}
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260403_050628_c4e32401-fab4-4a27-b7a8-6e9291cd5959.mp4"
        className="absolute left-1/2 top-0 -translate-x-1/2 w-[115%] h-[115%] max-w-none object-cover object-top transition-none"
        muted
        playsInline
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
        onLoadedData={handleLoadedData}
        style={{ opacity: 0 }}
      />
    </div>
  );
};

const NavBar = () => {
  return (
    <nav className="relative z-10 w-full px-[120px] py-[16px] flex items-center justify-between">
      <div className="font-schibsted font-semibold text-[24px] tracking-[-1.44px] text-white">
        MapsMine
      </div>

      <div className="flex items-center gap-8 font-schibsted font-medium text-[16px] tracking-[-0.2px] text-white">
        <button className="hover:text-gray-300 transition-colors">Product</button>
        <button className="flex items-center gap-1 hover:text-gray-300 transition-colors">
          Features <ChevronDown />
        </button>
        <button className="hover:text-gray-300 transition-colors">API</button>
        <button className="hover:text-gray-300 transition-colors">Docs</button>
        <button className="hover:text-gray-300 transition-colors">Contact</button>
      </div>

      <div className="flex items-center gap-2 font-schibsted font-medium text-[16px] tracking-[-0.2px]">
        <button className="w-[110px] h-10 rounded-lg text-white hover:bg-white/10 transition-colors">
          Get Started
        </button>
        <button className="w-[110px] h-10 rounded-lg bg-white text-black hover:bg-gray-200 transition-colors">
          Dashboard
        </button>
      </div>
    </nav>
  );
};

const HeroHeader = () => {
  return (
    <div className="flex flex-col items-center gap-[34px]">
      {/* Badge Component */}
      <div className="inline-flex items-center p-1 pr-4 bg-black/20 backdrop-blur-md rounded-full shadow-lg border border-white/20 font-inter font-normal text-[14px]">
        <div className="flex items-center gap-1.5 bg-white text-black px-3 py-1 rounded-full mr-3">
          <StarIcon />
          <span className="font-medium">Live</span>
        </div>
        <span className="text-white">Google Maps scraping with export-ready business data</span>
      </div>

      {/* Titles */}
      <div className="flex flex-col items-center text-center">
        <h1 className="font-fustat font-bold text-[80px] tracking-[-4.8px] leading-none text-white mb-6">
          Extract Google Maps Leads at Scale
        </h1>
        <p className="font-fustat font-medium text-[20px] tracking-[-0.4px] text-white/80 w-[542px] max-w-[736px]">
          Search any business category and location, automate real Chrome scraping, and export clean business listings with contact details, ratings, hours, and maps links.
        </p>
      </div>
    </div>
  );
};

const SearchInputBox = ({
  query,
  setQuery,
  limit,
  setLimit,
  loading,
  scrapeStatus,
  processedListings,
  targetListings,
  downloadReady,
  errorMessage,
  onRunScrape,
  onDownload,
}) => {
  const isJobActive = loading || ['Queued', 'Running'].includes(scrapeStatus);

  return (
    <div className="w-full max-w-[728px] h-[260px] bg-[rgba(0,0,0,0.24)] backdrop-blur-md rounded-[18px] p-3 flex flex-col shadow-2xl mt-[44px]">
      {/* Top Row */}
      <div className="flex justify-between items-center px-2 mb-2.5 font-schibsted font-medium text-[12px] text-white">
        <div className="flex items-center gap-3">
          <span className="opacity-90">Ready for 50+ listings</span>
          <button
            onClick={onDownload}
            disabled={!downloadReady}
            className="bg-[rgba(90,225,76,0.89)] text-black px-2 py-0.5 rounded shadow-sm hover:brightness-105 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Export
          </button>
          <div className="flex items-center gap-1">
            <span className="opacity-90">Limit</span>
            <input
              type="number"
              min={1}
              max={500}
              value={limit}
              onChange={(e) => setLimit(Math.max(1, Number(e.target.value) || 50))}
              className="w-16 h-6 rounded px-2 text-black outline-none"
              disabled={isJobActive}
            />
          </div>
        </div>
        <div className="flex items-center gap-1.5 opacity-90">
          <SparkleIcon />
          <span>Powered by Chrome Automation + AI</span>
        </div>
      </div>

      {/* Main Input Area */}
      <div className="flex-1 bg-[#ffffff] rounded-[12px] shadow-sm p-3 flex flex-col">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Enter a search like "AC repair services in Dubai" and choose how many listings to extract...'
          className="w-full flex-1 resize-none outline-none font-noto text-[16px] text-black placeholder:text-[rgba(0,0,0,0.6)] bg-transparent"
          disabled={isJobActive}
        />

        <div className="mt-2 px-1 space-y-1">
          <p className="font-schibsted text-[12px] text-[#444]">
            Status: <span className="font-semibold">{scrapeStatus}</span>
          </p>
          {['Queued', 'Running', 'Completed'].includes(scrapeStatus) && (
            <p className="font-schibsted text-[12px] text-[#555]">
              Processing {processedListings} / {targetListings || limit} listings...
            </p>
          )}
          {errorMessage && (
            <p className="font-schibsted text-[12px] text-red-600">{errorMessage}</p>
          )}
          {downloadReady && (
            <button
              onClick={onDownload}
              className="font-schibsted text-[12px] px-2 py-1 rounded bg-black text-white hover:bg-gray-800 transition-colors"
            >
              Download Results
            </button>
          )}
        </div>

        {/* Bottom Row */}
        <div className="flex justify-between items-end mt-2">
          {/* Left Action Buttons */}
          <div className="flex gap-2">
            <button
              onClick={onRunScrape}
              disabled={isJobActive}
              className="bg-[#f8f8f8] hover:bg-gray-200 transition-colors h-8 px-2.5 rounded-[6px] flex items-center gap-1.5 text-[#505050] font-schibsted font-medium text-[13px] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <VoiceIcon />
              {isJobActive ? 'Scraping...' : 'Run Scrape'}
            </button>
          </div>

          {/* Right Elements */}
          <div className="flex items-center gap-4">
            <span className="font-schibsted text-[12px] text-[#808080]">
              JSON + CSV + XLSX
            </span>
            <button
              onClick={onRunScrape}
              disabled={isJobActive}
              className="w-[36px] h-[36px] bg-black rounded-full flex items-center justify-center text-white hover:bg-gray-800 transition-colors shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <UpArrow />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState('');
  const [scrapeStatus, setScrapeStatus] = useState('Idle');
  const [processedListings, setProcessedListings] = useState(0);
  const [targetListings, setTargetListings] = useState(50);
  const [downloadReady, setDownloadReady] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleRunScrape = async () => {
    if (loading || ['Queued', 'Running'].includes(scrapeStatus)) return;

    const cleanedQuery = query.trim();
    if (!cleanedQuery) {
      setErrorMessage('Please enter a search query to run scraping.');
      return;
    }

    try {
      setLoading(true);
      setErrorMessage('');
      setDownloadReady(false);
      setProcessedListings(0);
      setTargetListings(limit);
      setScrapeStatus('Queued');

      const response = await fetch(`${API_BASE}/scrape`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: cleanedQuery,
          limit,
          headless: true,
          workers: 1,
          format: 'xlsx',
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with ${response.status}`);
      }

      const data = await response.json();
      if (!data?.job_id) {
        throw new Error('Backend did not return job_id.');
      }

      setJobId(data.job_id);
      setScrapeStatus(formatStatus(data.status || 'queued'));
    } catch (error) {
      setScrapeStatus('Failed');
      setLoading(false);
      setErrorMessage(error?.message || 'Failed to start scrape job.');
    }
  };

  const handleDownload = () => {
    if (!jobId || !downloadReady) return;
    window.open(`${API_BASE}/scrape/${jobId}/download`, '_blank', 'noopener,noreferrer');
  };

  useEffect(() => {
    if (!jobId) return;

    let isCancelled = false;
    let intervalId = null;

    const pollStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/scrape/${jobId}`);
        if (!response.ok) {
          throw new Error(`Status check failed with ${response.status}`);
        }

        const data = await response.json();
        if (isCancelled) return;

        const nextStatus = formatStatus(data?.status || 'running');
        const processed = Number(data?.progress?.processed_listings || 0);
        const target = Number(data?.progress?.target || targetListings || limit);

        setScrapeStatus(nextStatus);
        setProcessedListings(processed);
        setTargetListings(target);

        if (nextStatus === 'Completed') {
          setLoading(false);
          setDownloadReady(true);
          if (intervalId) clearInterval(intervalId);
        }

        if (nextStatus === 'Failed') {
          setLoading(false);
          setDownloadReady(false);
          setErrorMessage(data?.error || 'Scraping failed on the server.');
          if (intervalId) clearInterval(intervalId);
        }
      } catch (error) {
        if (isCancelled) return;
        setScrapeStatus('Failed');
        setLoading(false);
        setDownloadReady(false);
        setErrorMessage(error?.message || 'Failed while polling scrape status.');
        if (intervalId) clearInterval(intervalId);
      }
    };

    pollStatus();
    intervalId = window.setInterval(pollStatus, 2000);

    return () => {
      isCancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [jobId, limit]);

  return (
    <>
      {/* Font imports via style tag to ensure they load independently */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        @import url('https://fonts.googleapis.com/css2?family=Fustat:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Noto+Sans:wght@400;500;600;700&family=Schibsted+Grotesk:wght@400;500;600;700&display=swap');
        
        .font-fustat { font-family: 'Fustat', sans-serif; }
        .font-inter { font-family: 'Inter', sans-serif; }
        .font-noto { font-family: 'Noto Sans', sans-serif; }
        .font-schibsted { font-family: 'Schibsted Grotesk', sans-serif; }
      `,
        }}
      />

      <main className="relative min-h-screen w-full overflow-hidden bg-black flex flex-col">
        <VideoBackground />

        <NavBar />

        {/* Hero Container with 60px gap from Nav, and internal -50px negative margin adjustment */}
        <div className="relative z-10 w-full flex-1 flex flex-col items-center mt-[60px]">
          <div className="-mt-[50px] w-full flex flex-col items-center px-[120px]">
            <HeroHeader />
            <SearchInputBox
              query={query}
              setQuery={setQuery}
              limit={limit}
              setLimit={setLimit}
              loading={loading}
              scrapeStatus={scrapeStatus}
              processedListings={processedListings}
              targetListings={targetListings}
              downloadReady={downloadReady}
              errorMessage={errorMessage}
              onRunScrape={handleRunScrape}
              onDownload={handleDownload}
            />
          </div>
        </div>
      </main>
    </>
  );
}
