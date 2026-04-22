'use client';
import { useTheme } from './ThemeProvider';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      id="theme-toggle-btn"
      onClick={toggleTheme}
      className="theme-toggle-btn"
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
    >
      <div className={`toggle-track ${isDark ? 'dark' : 'light'}`}>
        {/* Stars (visible in dark mode) */}
        <div className={`stars-container ${isDark ? 'visible' : 'hidden'}`}>
          <span className="star star-1" />
          <span className="star star-2" />
          <span className="star star-3" />
        </div>

        {/* Cloud puffs (visible in light mode) */}
        <div className={`clouds-container ${!isDark ? 'visible' : 'hidden'}`}>
          <span className="cloud cloud-1" />
          <span className="cloud cloud-2" />
        </div>

        {/* The celestial body (sun/moon) */}
        <div className={`celestial-body ${isDark ? 'moon' : 'sun'}`}>
          {/* Moon craters */}
          <div className={`crater crater-1 ${isDark ? 'visible' : 'hidden'}`} />
          <div className={`crater crater-2 ${isDark ? 'visible' : 'hidden'}`} />
          <div className={`crater crater-3 ${isDark ? 'visible' : 'hidden'}`} />

          {/* Sun rays */}
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className={`sun-ray ${!isDark ? 'visible' : 'hidden'}`}
              style={{ transform: `rotate(${i * 45}deg)` }}
            />
          ))}
        </div>
      </div>
    </button>
  );
}
