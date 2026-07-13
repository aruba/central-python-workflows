/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '1.5rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      fontFamily: {
        sans: [
          'Geist Variable',
          'Geist',
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
        mono: [
          'Geist Mono Variable',
          'Geist Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'monospace',
        ],
      },
      letterSpacing: {
        // Vercel-style aggressive negative tracking on display sizes.
        'display-xl': '-0.05em',
        'display-lg': '-0.04em',
        'display-md': '-0.03em',
      },
      colors: {
        border: 'oklch(var(--border) / <alpha-value>)',
        input: 'oklch(var(--input) / <alpha-value>)',
        ring: 'oklch(var(--ring) / <alpha-value>)',
        background: 'oklch(var(--background) / <alpha-value>)',
        foreground: 'oklch(var(--foreground) / <alpha-value>)',
        primary: {
          DEFAULT: 'oklch(var(--primary) / <alpha-value>)',
          foreground: 'oklch(var(--primary-foreground) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'oklch(var(--secondary) / <alpha-value>)',
          foreground: 'oklch(var(--secondary-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT: 'oklch(var(--destructive) / <alpha-value>)',
          foreground: 'oklch(var(--destructive-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT: 'oklch(var(--muted) / <alpha-value>)',
          foreground: 'oklch(var(--muted-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'oklch(var(--accent) / <alpha-value>)',
          foreground: 'oklch(var(--accent-foreground) / <alpha-value>)',
        },
        popover: {
          DEFAULT: 'oklch(var(--popover) / <alpha-value>)',
          foreground: 'oklch(var(--popover-foreground) / <alpha-value>)',
        },
        card: {
          DEFAULT: 'oklch(var(--card) / <alpha-value>)',
          foreground: 'oklch(var(--card-foreground) / <alpha-value>)',
        },
        // Semantic status scale (health + alert severity). Solid: bg-success.
        // Soft badge: bg-warning/15 text-warning. Theme-aware via CSS vars.
        success: 'oklch(var(--success) / <alpha-value>)',
        warning: 'oklch(var(--warning) / <alpha-value>)',
        danger: 'oklch(var(--danger) / <alpha-value>)',
        info: 'oklch(var(--info) / <alpha-value>)',
      },
      borderRadius: {
        lg: 'calc(var(--radius) + 4px)', // 10px — slightly larger card chrome
        md: 'calc(var(--radius) + 2px)', // 8px — marketing-radius
        sm: 'var(--radius)',             // 6px — in-app default
        xs: 'calc(var(--radius) - 2px)', // 4px
      },
      boxShadow: {
        // Vercel-style stacked shadows: multiple small offsets + inset hairline.
        'stack-1':
          '0 0 0 1px rgba(0, 0, 0, 0.04), 0 1px 1px rgba(0, 0, 0, 0.02), 0 2px 2px rgba(0, 0, 0, 0.03)',
        'stack-2':
          '0 0 0 1px rgba(0, 0, 0, 0.04), 0 2px 2px rgba(0, 0, 0, 0.04), 0 8px 8px -8px rgba(0, 0, 0, 0.05)',
        'stack-3':
          '0 0 0 1px rgba(0, 0, 0, 0.05), 0 2px 2px rgba(0, 0, 0, 0.05), 0 8px 16px -4px rgba(0, 0, 0, 0.08)',
      },
    },
  },
  plugins: [],
}
