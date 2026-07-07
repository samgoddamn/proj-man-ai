# Plan: Dark mode-toggle i frontend

Slug: `dark-mode`  
Scope: **Frontend only.** Inga backend-, DTO-, modell- eller migrationsändringar.

## Mål
Lägga till en **dark mode-toggle** i `apps/web` som:
- följer befintlig stil (Tailwind-klasser + små UI-primitiver),
- minimerar förändringsyta men täcker alla nuvarande vyer,
- sparar användarens val och undviker tema-flash vid sidladdning.

## Kartläggning av nuvarande konventioner
- Appen kör App Router med global shell i `apps/web/app/layout.tsx`.
- Global styling ligger i `apps/web/app/globals.css`; idag är temat låst till ljust läge:
  - `:root { color-scheme: light; }`
  - `body` använder ljusa `slate`-färger.
- UI byggs med Tailwind-klasser direkt i sidor + återanvändbara primitiver i
  `apps/web/components/ui/primitives.tsx`.
- Ingen befintlig theme-provider/context finns.
- Klientpersistens använder `localStorage`-mönster i `apps/web/lib/auth.ts`
  (window-guard + enkla nycklar/funktioner).

## Föreslagen minsta robusta implementation

### 1) Theming-strategi
- Använd **class-baserat tema** (`dark` på `<html>`) i stället för endast media-query.
- Lägg till `darkMode: "class"` i `apps/web/tailwind.config.ts`.
- Behåll dagens utility-first-mönster; lägg till `dark:`-varianter där komponenter/sidor
  använder hårdkodade ljusa `slate`/`white`-klasser.

### 2) State och persistens
- Ny klientmodul: `apps/web/lib/theme.ts`
  - `THEME_KEY = "ai_pm_theme"`
  - `type Theme = "light" | "dark"`
  - `getStoredTheme()` / `setStoredTheme(theme)`
  - `resolveInitialTheme()`:
    1. använd sparat val om det finns,
    2. annars fallback till `matchMedia("(prefers-color-scheme: dark)")`.
  - `applyTheme(theme)` togglar `document.documentElement.classList` och sätter
    `document.documentElement.style.colorScheme` till `"light"`/`"dark"`.

### 3) Undvik FOUC (flash of un-themed content)
- I `apps/web/app/layout.tsx`: lägg in ett litet inline-script i `<head>` som läser
  `localStorage` + `prefers-color-scheme` och sätter `html.dark` före hydration.
- Headern behålls som gemensam plats för kontrollen.

### 4) Toggle-komponent
- Ny komponent: `apps/web/components/ThemeToggle.tsx` (`"use client"`).
- Ansvar:
  - läsa initialt tema via `resolveInitialTheme()`,
  - toggla mellan light/dark,
  - persistens via `setStoredTheme`,
  - uppdatera DOM via `applyTheme`.
- Integrera i `apps/web/components/HeaderActions.tsx` så togglen är synlig både inloggad
  och utloggad.

### 5) Uppdatera färgklasser för dark mode
För minsta robusthet uppdateras endast befintliga filer med explicita ljusklasser:
- `apps/web/app/layout.tsx`
- `apps/web/app/globals.css`
- `apps/web/components/ui/primitives.tsx`
- `apps/web/components/HeaderActions.tsx`
- `apps/web/app/page.tsx`
- `apps/web/app/login/page.tsx`
- `apps/web/app/projects/new/page.tsx`
- `apps/web/app/projects/[id]/page.tsx`
- `apps/web/app/projects/[id]/generating/page.tsx`
- `apps/web/app/projects/[id]/kanban/page.tsx`

Mönster: behåll existerande klasser och lägg till `dark:`-motsvarigheter (inte full
design-omtag), t.ex. bakgrunder, border, sekundär text och “ghost”-knappar.

## Tillgänglighetskrav för togglen
- Semantisk kontroll: `<button type="button">`.
- Tydligt namn via `aria-label` (t.ex. “Byt till mörkt/ljust läge”).
- Tillstånd via `aria-pressed` (true när dark är aktiv).
- Full tangentbordsstöd (Enter/Space fungerar implicit på button).
- Synlig fokusindikator i både ljust och mörkt läge (befintligt fokusmönster med ring).
- Kontrast ska vara minst WCAG AA för text/ikon mot bakgrund i båda temana.
- Klickyta minst ~40x40 px.

## API/Backend/DB
- **Inga ändringar** i FastAPI-endpoints, DTO:er, SQLAlchemy-modeller eller Alembic.

## Leveransresultat
- En global toggle i headern som fungerar på alla sidor.
- Användarens tema sparas mellan sidladdningar/sessioner.
- Ingen märkbar tema-flash vid initial render.
