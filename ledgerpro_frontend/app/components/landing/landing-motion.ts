/** Shared Framer Motion variants — use site-wide for consistency */
export const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.06, ease: 'easeOut' as const },
  }),
};

export const fadeUpWord = {
  hidden: { opacity: 0, y: 12 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, delay: i * 0.05, ease: 'easeOut' as const },
  }),
};

export const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

export const hoverLift = {
  whileHover: { y: -4, transition: { duration: 0.25 } },
};

export const viewportOnce = { once: true, margin: '-60px' as const };
