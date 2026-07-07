# Review: dark-mode

## Critical

Inga kritiska problem identifierade.

## Major

### 1) Tidig klick-interaktion kunde toggla fel tema innan klientinit var klar (**fixad**)

**Problemkod (före fix), `apps/web/components/ThemeToggle.tsx`:**
```tsx
const [theme, setTheme] = useState<Theme | null>(null);
const isDark = theme === "dark";
...
onClick={() => {
  const nextTheme: Theme = isDark ? "light" : "dark";
  applyTheme(nextTheme);
  setStoredTheme(nextTheme);
  setTheme(nextTheme);
}}
```

När `theme` fortfarande var `null` blev `isDark === false`. Om sidan redan låg i dark mode via SSR-initscript kunde ett snabbt första klick försöka sätta `dark` igen i stället för att växla till `light` (felaktig första interaktion).

**Åtgärd:** togglen är nu inaktiv tills tema är initierat (`disabled={!isReady}`), har neutral aria-label under init, och klickhanteraren skyddar mot tidig körning.

### 2) Oskyddad `localStorage`-access kunde krascha temainit i vissa miljöer (**fixad**)

**Problemkod (före fix), `apps/web/app/layout.tsx`:**
```tsx
const stored = localStorage.getItem(key);
```

Och i `apps/web/lib/theme.ts`:
```ts
const stored = localStorage.getItem(THEME_KEY);
localStorage.setItem(THEME_KEY, theme);
```

I miljöer där storage är blockerad (t.ex. privacy-lägen/policys) kan `localStorage` kasta. Det gav regressionsrisk: initscript kunde avbrytas innan klass/cascade sattes, och togglen kunde få runtime-fel.

**Åtgärd:** access till `window.localStorage` är nu guardad med `try/catch` både i initscript och i tema-helpern, med säker fallback till systempreferens/runtime-tema.

## Minor

### 1) Kontrast i dark mode för rekommendationstext kunde bli låg (**fixad**)

**Problemkod (före fix), `apps/web/app/projects/[id]/page.tsx`:**
```tsx
<p className="text-sm text-brand-700">→ {r.recommendation}</p>
```

`text-brand-700` på mörk bakgrund riskerar låg läsbarhet.

**Åtgärd:** kompletterat med dark-variant (`dark:text-brand-300`) för bättre kontrast.
