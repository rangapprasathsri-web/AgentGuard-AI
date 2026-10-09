# AgentGuard AI Design Tokens

These design tokens are matched against the reference implementation at 1440px viewport (`https://nevora-eight.vercel.app`) and adapted for the AgentGuard AI governance platform.

## Layout & Containers
- **Content Container**: `1200px` max-width (`max-w-[1200px]`), centered (`mx-auto`).
- **Section Spacing**: Generous vertical rhythm `120px` to `160px` (`pt-32` to `pt-40` / `mt-32` to `mt-40`).
- **Panels**: Radius `40px` - `48px` (`rounded-[40px]`, `rounded-[48px]`), borderless, no heavy shadows.
- **Inner Cards**: Radius `20px` - `24px` (`rounded-[22px]`, `rounded-[24px]`), soft diffuse shadow (`shadow-[0_8px_30px_rgba(0,0,0,0.05)]`).
- **Interactive Elements Radius**: Full pill (`rounded-full`) for CTA buttons and badges; `14px` for inputs/controls.

## Typography
- **Font Stack**: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif` (Locally bundled or system font stack; zero external CDNs).
- **Headlines**: Inter Bold (`font-bold` / `font-semibold`), very tight tracking (`tracking-[-0.04em]` to `-0.05em`), line-height `0.98` to `1.05`.
  - Hero: `text-[56px] sm:text-[80px] lg:text-[100px]`, line-height `0.98`, two lines.
  - Section Headlines: `text-4xl sm:text-[54px] lg:text-[64px]`, line-height `1.02`.
  - Card Headlines: `text-[32px]`, line-height `1.1`, tracking `-0.03em`.
- **Eyebrow Labels**: `text-[15px] font-medium text-[#6938EF]` (sentence case, small purple text).
- **Body & Subtitles**: `text-[17px]` to `text-[20px]`, line-height `1.6`, color `#73737D`.
- **Small Badges & Pills**: `text-[11px]` to `text-[13px]`, tracking `0.06em` for uppercase labels.

## Color Palette (Light Mode)
- **Page Background**: `#FFFFFF`
- **Primary Ink (Text)**: `#1D1D20`
- **Muted Gray**: `#73737D` (borders/hairline `#ECECF0` / `#D2D2D7`)
- **Accent Purple (Brand)**: `#6938EF`
- **Accent Purple Hover**: `#5728D8`
- **Accent Purple Soft**: `#F3EFFE` (chip background)
- **Soft Panel Gray (Surface)**: `#F5F5F7`
- **Cyan / Learn Panel**: `#E4F5F8`
- **Cyan / Learn Ink**: `#0A7A8A`
- **Status OK (Green)**: `#1E7B34` (Soft: `#E9F7EE`, Dot: `#34C759`)
- **Status Review / Warn (Amber)**: `#8A4B00` (Soft: `#FFF6E8`, Dot: `#FF9F0A`, Border: `#FF9F0A4D`)
- **Status Block / Bad (Red)**: `#C4001A` (Soft: `#FFECEE`, Dot: `#FF3B30`)
- **Metric Highlight Yellow**: `#FFF3B0` (chip highlight for policy excerpts)

## Color Palette (Dark Mode - `data-theme="dark"`)
- **Page Background**: `#0B0B0C`
- **Card Background**: `#151517`
- **Surface Panel**: `#1C1C1E`
- **Primary Ink (Text)**: `#F5F5F7`
- **Muted Gray**: `#A1A1A6`
- **Borders & Lines**: `#2C2C2E`
- **Accent Purple**: `#7C5CF5`
- **Cyan Panel**: `#10292D`
- **Cyan Ink**: `#7DD3DF`
- **Status OK**: `#4ADE80` (Soft: `#10261A`)
- **Status Warn**: `#FBBF24` (Soft: `#2B2110`)
- **Status Bad**: `#FF6B6B` (Soft: `#2E1416`)
- **Metric Highlight**: `#5C4A00`

## Motion & Accessibility
- **Keyframes**: `rise` (`0% { opacity: 0; transform: translateY(12px) } to { opacity: 1; transform: none }`), duration 0.6s.
- **Card Hover**: Subtle lift (`hover:-translate-y-0.5 transition-transform duration-200`).
- **Reduced Motion**: Disables all transitions and transforms when `prefers-reduced-motion: reduce` is active.
