const COLORS = {
  JavaScript: '#f1e05a', TypeScript: '#3178c6', Python: '#3572A5', Java: '#b07219',
  'C++': '#f34b7d', C: '#555555', 'C#': '#178600', Go: '#00ADD8', Rust: '#dea584',
  Ruby: '#701516', PHP: '#4F5D95', Swift: '#F05138', Kotlin: '#A97BFF', Dart: '#00B4AB',
  HTML: '#e34c26', CSS: '#563d7c', SCSS: '#c6538c', Vue: '#41b883', Svelte: '#ff3e00',
  Shell: '#89e051', Lua: '#000080', 'Jupyter Notebook': '#DA5B0B', R: '#198CE7',
  Scala: '#c22d40', Elixir: '#6e4a7e', Haskell: '#5e5086', Zig: '#ec915c',
  'Objective-C': '#438eff', Astro: '#ff5a03', MDX: '#fcb32c', Nix: '#7e7eff',
};
export const langColor = (name) => COLORS[name] || '#8b8b9e';
