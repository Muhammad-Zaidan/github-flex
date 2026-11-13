import type { Project } from '../core/types';
import type { Lang } from '../i18n';
import { B, CMP, CTU, MATH, NC, NO, OR, OUT, P, RST, SET, TON, k, tag } from './dsl';

export type Category = 'motor' | 'process' | 'general';

export interface Param {
  key: string;
  label: { id: string; en: string };
  type: 'number' | 'boolean';
  default: number | boolean;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
}

export type Params = Record<string, number | boolean>;

export interface Template {
  id: string;
  category: Category;
  title: { id: string; en: string };
  summary: { id: string; en: string };
  params: Param[];
  build: (p: Params, lang: Lang) => Project;
}

const sec = (key: string, id: string, en: string, def: number, min = 0.1, max = 600): Param =>
  ({ key, label: { id, en }, type: 'number', default: def, min, max, step: 0.1, unit: 's' });
const bool = (key: string, id: string, en: string, def: boolean): Param => ({ key, label: { id, en }, type: 'boolean', default: def });
const num = (key: string, id: string, en: string, def: number, min: number, max: number): Param =>
  ({ key, label: { id, en }, type: 'number', default: def, min, max, step: 1 });

const ms = (s: number | boolean) => Math.round(Number(s) * 1000);

/** Standard START/STOP/overload trio shared by motor circuits. */
function motorInputs(b: B) {
  const start = b.input('START', b.L('Tombol start (NO)', 'Start push button (NO)'));
  const stop = b.input('STOP', b.L('Tombol stop (dipasang NO, di program pakai NC)', 'Stop push button (wired NO, used as NC in program)'));
  const ol = b.input('OL', b.L('Kontak bantu overload TOR 97-98, ON saat trip', 'Overload relay aux contact 97-98, ON when tripped'), 'switch');
  return { start, stop, ol };
}

function lamps(b: B, run: string, ol: string) {
  const hRun = b.output('H_RUN', b.L('Lampu hijau: motor jalan', 'Green lamp: motor running'));
  const hTrip = b.output('H_TRIP', b.L('Lampu merah/kuning: overload trip', 'Red/amber lamp: overload tripped'));
  b.r([NO(run)], [OUT(hRun)], b.L('Lampu jalan', 'Run lamp'), b.L('Lampu hijau menyala selama motor jalan.', 'Green lamp is on while the motor runs.'));
  b.r([NO(ol)], [OUT(hTrip)], b.L('Lampu trip', 'Trip lamp'), b.L('Lampu trip menyala selama overload trip, sebagai tanda operator harus reset TOR.', 'Trip lamp is on while the overload is tripped, telling the operator to reset the relay.'));
}

export const TEMPLATES: Template[] = [
  {
    id: 'dol',
    category: 'motor',
    title: { id: 'DOL start–stop', en: 'DOL start–stop' },
    summary: { id: 'Motor langsung dengan self-holding, stop, dan proteksi overload.', en: 'Direct-on-line motor with self-holding, stop and overload protection.' },
    params: [bool('lamps', 'Lampu indikator', 'Indicator lamps', true)],
    build: (p, lang) => {
      const b = new B(lang);
      const { start, stop, ol } = motorInputs(b);
      const km = b.output('KM1', b.L('Kontaktor motor', 'Motor contactor'));
      b.r([OR(NO(start), NO(km)), NC(stop), NC(ol)], [OUT(km)], b.L('Self-holding KM1', 'KM1 self-holding'),
        b.L('START menghidupkan KM1. Kontak KM1 yang paralel dengan START "mengunci" supaya motor tetap jalan setelah tombol dilepas. STOP atau overload memutus rangkaian.',
          'START energises KM1. The KM1 contact in parallel with START latches it so the motor keeps running after the button is released. STOP or overload breaks the circuit.'));
      if (p.lamps) lamps(b, km, ol);
      return b.project(b.L('Motor DOL start–stop', 'DOL motor start–stop'), b.L('Starter motor langsung (DOL)', 'Direct-on-line motor starter'), 'dol');
    },
  },
  {
    id: 'star-delta',
    category: 'motor',
    title: { id: 'Star–delta starter', en: 'Star–delta starter' },
    summary: { id: 'Start bintang, pindah ke segitiga setelah timer, dengan interlock dan jeda transisi.', en: 'Start in star, switch to delta after a timer, with interlock and transition gap.' },
    params: [
      sec('starTime', 'Waktu bintang', 'Star time', 6, 1, 60),
      num('gapMs', 'Jeda transisi', 'Transition gap', 100, 50, 500),
      bool('lamps', 'Lampu indikator', 'Indicator lamps', true),
    ],
    build: (p, lang) => {
      const b = new B(lang);
      const { start, stop, ol } = motorInputs(b);
      const run = b.mem('M_RUN', b.L('Memori perintah jalan', 'Run command memory'));
      const kmM = b.output('KM_MAIN', b.L('Kontaktor main (K1)', 'Main contactor (K1)'));
      const kmS = b.output('KM_STAR', b.L('Kontaktor bintang (K3)', 'Star contactor (K3)'));
      const kmD = b.output('KM_DELTA', b.L('Kontaktor segitiga (K2)', 'Delta contactor (K2)'));
      const t1 = b.timer('T_STAR', b.L('Lama start bintang', 'Star duration'));
      const t2 = b.timer('T_GAP', b.L('Jeda bintang → segitiga', 'Star → delta gap'));
      b.r([OR(NO(start), NO(run)), NC(stop), NC(ol)], [OUT(run)], b.L('Perintah jalan', 'Run command'),
        b.L('START mengunci memori M_RUN. STOP atau overload melepasnya, dan semua kontaktor ikut mati.', 'START latches M_RUN. STOP or overload releases it, dropping every contactor.'));
      b.r([NO(run)], [OUT(kmM), TON(t1, ms(p.starTime))], b.L('Main + timer bintang', 'Main + star timer'),
        b.L(`Selama M_RUN aktif, kontaktor main hidup dan timer T_STAR mulai menghitung ${p.starTime} detik.`, `While M_RUN is on the main contactor is energised and T_STAR starts counting ${p.starTime} s.`));
      b.r([NO(run), NC(t1), NC(kmD)], [OUT(kmS)], b.L('Kontaktor bintang', 'Star contactor'),
        b.L('Bintang hidup di awal dan mati saat T_STAR selesai. Kontak NC KM_DELTA adalah interlock: bintang tidak boleh hidup bersamaan dengan segitiga.', 'Star is on at start and drops when T_STAR is done. The NC KM_DELTA contact is the interlock: star and delta must never be on together.'));
      b.r([NO(run), NO(t1)], [TON(t2, Number(p.gapMs))], b.L('Jeda transisi', 'Transition gap'),
        b.L(`Setelah bintang lepas, tunggu ${p.gapMs} ms supaya busur api di kontaktor bintang padam sebelum segitiga masuk.`, `After star drops, wait ${p.gapMs} ms so the arc in the star contactor clears before delta closes.`));
      b.r([NO(run), NO(t2), NC(kmS)], [OUT(kmD)], b.L('Kontaktor segitiga', 'Delta contactor'),
        b.L('Segitiga hidup setelah jeda selesai, dan hanya jika bintang benar-benar sudah mati (interlock NC KM_STAR).', 'Delta closes after the gap, and only if star is really off (NC KM_STAR interlock).'));
      if (p.lamps) lamps(b, run, ol);
      return b.project(b.L('Star–delta starter', 'Star–delta starter'), b.L('Starter bintang-segitiga', 'Star-delta motor starter'), 'star-delta');
    },
  },
  {
    id: 'fwd-rev',
    category: 'motor',
    title: { id: 'Forward–reverse', en: 'Forward–reverse' },
    summary: { id: 'Putar kanan/kiri dengan interlock kontaktor dan tombol.', en: 'Forward/reverse rotation with contactor and push-button interlock.' },
    params: [bool('pbInterlock', 'Interlock tombol', 'Push-button interlock', true), bool('lamps', 'Lampu indikator', 'Indicator lamps', true)],
    build: (p, lang) => {
      const b = new B(lang);
      const fwd = b.input('FWD', b.L('Tombol putar maju', 'Forward push button'));
      const rev = b.input('REV', b.L('Tombol putar mundur', 'Reverse push button'));
      const stop = b.input('STOP', b.L('Tombol stop', 'Stop push button'));
      const ol = b.input('OL', b.L('Overload trip', 'Overload tripped'), 'switch');
      const kf = b.output('KM_FWD', b.L('Kontaktor maju', 'Forward contactor'));
      const kr = b.output('KM_REV', b.L('Kontaktor mundur', 'Reverse contactor'));
      const pbi = !!p.pbInterlock;
      b.r([OR(NO(fwd), NO(kf)), NC(stop), NC(ol), ...(pbi ? [NC(rev)] : []), NC(kr)], [OUT(kf)], b.L('Putar maju', 'Forward'),
        b.L(`FWD menghidupkan KM_FWD dengan self-holding. NC KM_REV adalah interlock kontaktor${pbi ? ', dan NC REV adalah interlock tombol' : ''}, supaya fasa tidak pernah terhubung singkat.`,
          `FWD energises KM_FWD with self-holding. NC KM_REV is the contactor interlock${pbi ? ' and NC REV the push-button interlock' : ''}, so the phases are never shorted.`));
      b.r([OR(NO(rev), NO(kr)), NC(stop), NC(ol), ...(pbi ? [NC(fwd)] : []), NC(kf)], [OUT(kr)], b.L('Putar mundur', 'Reverse'),
        b.L('Cerminan rung maju. Untuk pindah arah, tekan STOP dulu (atau langsung tombol arah lain jika interlock tombol aktif).', 'Mirror of the forward rung. To change direction press STOP first (or the other direction button when push-button interlock is on).'));
      if (p.lamps) {
        const hf = b.output('H_FWD', b.L('Lampu maju', 'Forward lamp'));
        const hr = b.output('H_REV', b.L('Lampu mundur', 'Reverse lamp'));
        b.r([NO(kf)], [OUT(hf)], b.L('Lampu maju', 'Forward lamp'), b.L('Menyala saat motor putar maju.', 'On while running forward.'));
        b.r([NO(kr)], [OUT(hr)], b.L('Lampu mundur', 'Reverse lamp'), b.L('Menyala saat motor putar mundur.', 'On while running in reverse.'));
      }
      return b.project(b.L('Motor forward–reverse', 'Forward–reverse motor'), b.L('Pembalik putaran motor', 'Motor reversing starter'), 'fwd-rev');
    },
  },
  {
    id: 'sequential',
    category: 'motor',
    title: { id: 'Sequential motor starter', en: 'Sequential motor starter' },
    summary: { id: 'Beberapa motor hidup berurutan dengan jeda waktu; satu STOP mematikan semua.', en: 'Several motors start one after another with a delay; one STOP stops them all.' },
    params: [num('motors', 'Jumlah motor', 'Number of motors', 3, 2, 8), sec('delay', 'Jeda antar motor', 'Delay between motors', 5, 0.5, 120)],
    build: (p, lang) => {
      const b = new B(lang);
      const { start, stop, ol } = motorInputs(b);
      const n = Number(p.motors);
      const run = b.mem('M_RUN', b.L('Memori jalan', 'Run memory'));
      const kms = Array.from({ length: n }, (_, i) => b.output(`KM${i + 1}`, b.L(`Kontaktor motor ${i + 1}`, `Motor ${i + 1} contactor`)));
      const ts = Array.from({ length: n - 1 }, (_, i) => b.timer(`T${i + 1}`, b.L(`Jeda sebelum motor ${i + 2}`, `Delay before motor ${i + 2}`)));
      b.r([OR(NO(start), NO(run)), NC(stop), NC(ol)], [OUT(run)], b.L('Perintah jalan', 'Run command'),
        b.L('START mengunci M_RUN. STOP atau overload salah satu motor mematikan seluruh urutan.', 'START latches M_RUN. STOP or any overload stops the whole sequence.'));
      b.r([NO(run)], [OUT(kms[0]), TON(ts[0], ms(p.delay))], b.L('Motor 1', 'Motor 1'),
        b.L(`Motor 1 langsung hidup, dan T1 mulai menghitung ${p.delay} detik untuk motor berikutnya.`, `Motor 1 starts immediately; T1 counts ${p.delay} s for the next motor.`));
      for (let i = 1; i < n; i++) {
        const outs = i < n - 1 ? [OUT(kms[i]), TON(ts[i], ms(p.delay))] : [OUT(kms[i])];
        b.r([NO(run), NO(ts[i - 1])], outs, b.L(`Motor ${i + 1}`, `Motor ${i + 1}`),
          b.L(`Motor ${i + 1} hidup setelah T${i} selesai${i < n - 1 ? `, lalu T${i + 1} mulai menghitung untuk motor ${i + 2}` : ''}.`,
            `Motor ${i + 1} starts when T${i} is done${i < n - 1 ? `, then T${i + 1} starts for motor ${i + 2}` : ''}.`));
      }
      return b.project(b.L(`Sequential starter ${n} motor`, `${n}-motor sequential starter`), b.L('Start motor berurutan', 'Sequential motor start'), 'sequential');
    },
  },
  {
    id: 'jog',
    category: 'motor',
    title: { id: 'Jogging + run', en: 'Jog + run' },
    summary: { id: 'Mode jalan terus dan jogging (jalan selama tombol ditekan).', en: 'Continuous run plus jog (runs only while held).' },
    params: [],
    build: (_p, lang) => {
      const b = new B(lang);
      const { start, stop, ol } = motorInputs(b);
      const jog = b.input('JOG', b.L('Tombol jogging', 'Jog push button'));
      const run = b.mem('M_RUN', b.L('Memori jalan terus', 'Continuous run memory'));
      const km = b.output('KM1', b.L('Kontaktor motor', 'Motor contactor'));
      b.r([OR(NO(start), NO(run)), NC(stop), NC(ol), NC(jog)], [OUT(run)], b.L('Mode jalan', 'Run mode'),
        b.L('START mengunci M_RUN. NC JOG mencegah jogging ikut mengunci motor.', 'START latches M_RUN. NC JOG keeps jogging from latching the motor.'));
      b.r([OR(NO(run), NO(jog)), NC(ol)], [OUT(km)], b.L('Kontaktor motor', 'Motor contactor'),
        b.L('Motor jalan saat M_RUN aktif atau selama JOG ditekan.', 'Motor runs while M_RUN is on or while JOG is held.'));
      return b.project(b.L('Motor jogging + run', 'Jog + run motor'), '', 'jog');
    },
  },
  {
    id: 'conveyor-count',
    category: 'process',
    title: { id: 'Conveyor penghitung produk', en: 'Product-counting conveyor' },
    summary: { id: 'Conveyor berhenti otomatis setelah N produk lewat sensor.', en: 'Conveyor stops automatically after N products pass the sensor.' },
    params: [num('batch', 'Jumlah per batch', 'Products per batch', 10, 1, 9999)],
    build: (p, lang) => {
      const b = new B(lang);
      const start = b.input('START', b.L('Tombol start', 'Start push button'));
      const stop = b.input('STOP', b.L('Tombol stop', 'Stop push button'));
      const sens = b.input('SENSOR', b.L('Sensor produk (photoelectric)', 'Product sensor (photoelectric)'), 'sensor');
      const reset = b.input('RESET', b.L('Reset hitungan', 'Reset count'));
      const run = b.mem('M_RUN', b.L('Conveyor jalan', 'Conveyor running'));
      const motor = b.output('MOTOR', b.L('Motor conveyor', 'Conveyor motor'));
      const full = b.output('H_FULL', b.L('Lampu batch penuh', 'Batch-full lamp'));
      const c1 = b.counter('C_BATCH', b.L('Penghitung produk', 'Product counter'));
      b.r([OR(NO(start), NO(run)), NC(stop), NC(c1)], [OUT(run)], b.L('Jalan conveyor', 'Conveyor run'),
        b.L('START menjalankan conveyor sampai STOP ditekan atau hitungan mencapai batch.', 'START runs the conveyor until STOP is pressed or the batch count is reached.'));
      b.r([NO(run)], [OUT(motor)], b.L('Motor', 'Motor'), b.L('Motor mengikuti status jalan.', 'Motor follows the run state.'));
      b.r([NO(run), NO(sens)], [CTU(c1, Number(p.batch), reset)], b.L('Hitung produk', 'Count products'),
        b.L(`Setiap produk yang lewat sensor menambah hitungan satu kali (pada tepi naik). Setelah ${p.batch} produk, C_BATCH ON. RESET mengosongkan hitungan.`,
          `Each product passing the sensor adds one count (on the rising edge). After ${p.batch} products C_BATCH turns on. RESET clears it.`));
      b.r([NO(c1)], [OUT(full)], b.L('Batch penuh', 'Batch full'), b.L('Lampu menyala saat batch penuh, lalu tekan RESET untuk batch berikutnya.', 'Lamp is on when the batch is full; press RESET for the next batch.'));
      return b.project(b.L('Conveyor penghitung produk', 'Product-counting conveyor'), '', 'conveyor-count');
    },
  },
  {
    id: 'tank-level',
    category: 'process',
    title: { id: 'Kontrol level tangki', en: 'Tank level control' },
    summary: { id: 'Pompa mengisi tangki dari level rendah sampai level tinggi (histeresis).', en: 'Pump fills the tank from low to high level (hysteresis).' },
    params: [bool('alarm', 'Alarm level kosong', 'Low-level alarm', true)],
    build: (p, lang) => {
      const b = new B(lang);
      const auto = b.input('AUTO', b.L('Selector auto', 'Auto selector'), 'switch');
      const low = b.input('LS_LOW', b.L('Sensor level rendah (ON = air di atas sensor)', 'Low level sensor (ON = water above it)'), 'switch');
      const high = b.input('LS_HIGH', b.L('Sensor level tinggi (ON = air di atas sensor)', 'High level sensor (ON = water above it)'), 'switch');
      const pump = b.output('PUMP', b.L('Pompa pengisi', 'Fill pump'));
      b.r([NO(auto), OR(NC(low), NO(pump)), NC(high)], [OUT(pump)], b.L('Pompa', 'Pump'),
        b.L('Saat air di bawah sensor rendah, pompa hidup dan mengunci dirinya sampai air menyentuh sensor tinggi. Di antara dua sensor, pompa mempertahankan status terakhirnya (histeresis).',
          'When water is below the low sensor the pump starts and holds itself until water reaches the high sensor. Between the sensors it keeps its last state (hysteresis).'));
      if (p.alarm) {
        const al = b.output('H_LOW', b.L('Lampu air kosong', 'Tank-empty lamp'));
        b.r([NC(low)], [OUT(al)], b.L('Alarm level rendah', 'Low level alarm'), b.L('Lampu menyala selama air di bawah sensor rendah.', 'Lamp is on while water is below the low sensor.'));
      }
      return b.project(b.L('Kontrol level tangki', 'Tank level control'), '', 'tank-level');
    },
  },
  {
    id: 'mixing',
    category: 'process',
    title: { id: 'Tangki mixing berurutan', en: 'Sequential mixing tank' },
    summary: { id: 'Isi → aduk selama T detik → kuras, dengan langkah SET/RESET.', en: 'Fill → mix for T seconds → drain, using SET/RESET steps.' },
    params: [sec('mix', 'Lama pengadukan', 'Mixing time', 10, 1, 3600)],
    build: (p, lang) => {
      const b = new B(lang);
      const start = b.input('START', b.L('Mulai siklus', 'Start cycle'));
      const stop = b.input('STOP', b.L('Hentikan siklus', 'Stop cycle'));
      const high = b.input('LS_HIGH', b.L('Sensor tangki penuh', 'Tank-full sensor'), 'switch');
      const low = b.input('LS_LOW', b.L('Sensor tangki masih berisi', 'Tank-not-empty sensor'), 'switch');
      const s1 = b.mem('S1_FILL', b.L('Langkah 1: isi', 'Step 1: fill'));
      const s2 = b.mem('S2_MIX', b.L('Langkah 2: aduk', 'Step 2: mix'));
      const s3 = b.mem('S3_DRAIN', b.L('Langkah 3: kuras', 'Step 3: drain'));
      const tm = b.timer('T_MIX', b.L('Lama aduk', 'Mixing time'));
      const vin = b.output('V_IN', b.L('Valve masuk', 'Inlet valve'));
      const mix = b.output('MIXER', b.L('Motor pengaduk', 'Mixer motor'));
      const vout = b.output('V_OUT', b.L('Valve keluar', 'Outlet valve'));
      b.r([P(start), NC(s1), NC(s2), NC(s3)], [SET(s1)], b.L('Mulai → isi', 'Start → fill'),
        b.L('START memulai langkah 1, tapi hanya jika tidak ada langkah yang sedang berjalan.', 'START begins step 1 only when no step is active.'));
      b.r([NO(s1), NO(high)], [SET(s2), RST(s1)], b.L('Penuh → aduk', 'Full → mix'),
        b.L('Saat tangki penuh, pindah dari langkah isi ke langkah aduk.', 'When the tank is full, move from fill to mix.'));
      b.r([NO(s2)], [TON(tm, ms(p.mix))], b.L('Timer aduk', 'Mix timer'), b.L(`Selama langkah aduk, T_MIX menghitung ${p.mix} detik.`, `During the mix step T_MIX counts ${p.mix} s.`));
      b.r([NO(s2), NO(tm)], [SET(s3), RST(s2)], b.L('Selesai aduk → kuras', 'Mixed → drain'), b.L('Setelah waktu aduk habis, pindah ke langkah kuras.', 'When mixing time is up, move to drain.'));
      b.r([NO(s3), NC(low)], [RST(s3)], b.L('Kosong → selesai', 'Empty → done'), b.L('Saat tangki kosong, siklus selesai dan siap START lagi.', 'When the tank is empty the cycle ends, ready for START again.'));
      b.r([NO(stop)], [RST(s1), RST(s2), RST(s3)], b.L('Stop', 'Stop'), b.L('STOP membatalkan semua langkah.', 'STOP cancels every step.'));
      b.r([NO(s1)], [OUT(vin)], b.L('Valve masuk', 'Inlet valve'), b.L('Valve masuk terbuka di langkah isi.', 'Inlet valve opens in the fill step.'));
      b.r([NO(s2)], [OUT(mix)], b.L('Pengaduk', 'Mixer'), b.L('Pengaduk jalan di langkah aduk.', 'Mixer runs in the mix step.'));
      b.r([NO(s3)], [OUT(vout)], b.L('Valve keluar', 'Outlet valve'), b.L('Valve keluar terbuka di langkah kuras.', 'Outlet valve opens in the drain step.'));
      return b.project(b.L('Tangki mixing', 'Mixing tank'), '', 'mixing');
    },
  },
  {
    id: 'filling',
    category: 'process',
    title: { id: 'Pengisian botol', en: 'Bottle filling' },
    summary: { id: 'Conveyor berhenti saat botol terdeteksi, isi selama T detik, lalu jalan lagi.', en: 'Conveyor stops at a bottle, fills for T seconds, then moves on.' },
    params: [sec('fill', 'Lama pengisian', 'Fill time', 3, 0.5, 60)],
    build: (p, lang) => {
      const b = new B(lang);
      const start = b.input('START', b.L('Tombol start', 'Start push button'));
      const stop = b.input('STOP', b.L('Tombol stop', 'Stop push button'));
      const bottle = b.input('BOTTLE', b.L('Sensor botol di bawah nozzle', 'Bottle-under-nozzle sensor'), 'sensor');
      const run = b.mem('M_RUN', b.L('Sistem jalan', 'System running'));
      const fill = b.mem('M_FILL', b.L('Sedang mengisi', 'Filling'));
      const tf = b.timer('T_FILL', b.L('Lama pengisian', 'Fill time'));
      const conv = b.output('CONVEYOR', b.L('Motor conveyor', 'Conveyor motor'));
      const valve = b.output('V_FILL', b.L('Valve pengisi', 'Fill valve'));
      b.r([OR(NO(start), NO(run)), NC(stop)], [OUT(run)], b.L('Sistem jalan', 'System run'), b.L('START/STOP dengan self-holding.', 'START/STOP with self-holding.'));
      b.r([NO(run), P(bottle)], [SET(fill)], b.L('Botol datang', 'Bottle arrives'),
        b.L('Tepi naik sensor botol (botol baru tiba) memulai pengisian.', 'The rising edge of the bottle sensor (a new bottle) starts filling.'));
      b.r([NO(fill)], [TON(tf, ms(p.fill))], b.L('Timer isi', 'Fill timer'), b.L(`Pengisian berlangsung ${p.fill} detik.`, `Filling lasts ${p.fill} s.`));
      b.r([OR(NO(tf), NC(run))], [RST(fill)], b.L('Selesai isi', 'Fill done'), b.L('Pengisian selesai saat timer habis atau sistem dihentikan.', 'Filling ends when the timer is done or the system stops.'));
      b.r([NO(run), NC(fill)], [OUT(conv)], b.L('Conveyor', 'Conveyor'), b.L('Conveyor jalan kecuali sedang mengisi.', 'Conveyor runs except while filling.'));
      b.r([NO(fill)], [OUT(valve)], b.L('Valve', 'Valve'), b.L('Valve terbuka selama mengisi.', 'Valve is open while filling.'));
      return b.project(b.L('Pengisian botol', 'Bottle filling'), '', 'filling');
    },
  },
  {
    id: 'traffic',
    category: 'general',
    title: { id: 'Lampu lalu lintas perempatan', en: 'Intersection traffic light' },
    summary: { id: 'Dua arah, siklus hijau–kuning–merah memakai rantai 4 timer.', en: 'Two directions, green–yellow–red cycle using a chain of 4 timers.' },
    params: [sec('green', 'Lama hijau', 'Green time', 10, 1, 300), sec('yellow', 'Lama kuning', 'Yellow time', 3, 1, 30)],
    build: (p, lang) => {
      const b = new B(lang);
      const on = b.input('RUN', b.L('Saklar on/off', 'On/off switch'), 'switch');
      const t1 = b.timer('T1', b.L('Hijau arah A', 'Green A'));
      const t2 = b.timer('T2', b.L('Kuning arah A', 'Yellow A'));
      const t3 = b.timer('T3', b.L('Hijau arah B', 'Green B'));
      const t4 = b.timer('T4', b.L('Kuning arah B', 'Yellow B'));
      const ga = b.output('A_GREEN', b.L('Hijau A', 'Green A'));
      const ya = b.output('A_YELLOW', b.L('Kuning A', 'Yellow A'));
      const ra = b.output('A_RED', b.L('Merah A', 'Red A'));
      const gb = b.output('B_GREEN', b.L('Hijau B', 'Green B'));
      const yb = b.output('B_YELLOW', b.L('Kuning B', 'Yellow B'));
      const rb = b.output('B_RED', b.L('Merah B', 'Red B'));
      const G = ms(p.green), Y = ms(p.yellow);
      b.r([NO(on), NC(t4)], [TON(t1, G)], b.L('Fase 1: hijau A', 'Phase 1: green A'),
        b.L('T1 berjalan selama RUN aktif. Saat T4 (fase terakhir) selesai, T1 reset sehingga siklus berulang.', 'T1 runs while RUN is on. When T4 (last phase) is done T1 resets, so the cycle repeats.'));
      b.r([NO(t1)], [TON(t2, Y)], b.L('Fase 2: kuning A', 'Phase 2: yellow A'), b.L('T2 mulai setelah T1 selesai.', 'T2 starts after T1.'));
      b.r([NO(t2)], [TON(t3, G)], b.L('Fase 3: hijau B', 'Phase 3: green B'), b.L('T3 mulai setelah T2 selesai.', 'T3 starts after T2.'));
      b.r([NO(t3)], [TON(t4, Y)], b.L('Fase 4: kuning B', 'Phase 4: yellow B'), b.L('T4 mulai setelah T3 selesai.', 'T4 starts after T3.'));
      b.r([NO(on), NC(t1)], [OUT(ga)], b.L('Hijau A', 'Green A'), b.L('Hijau A menyala sebelum T1 selesai.', 'Green A is on until T1 is done.'));
      b.r([NO(t1), NC(t2)], [OUT(ya)], b.L('Kuning A', 'Yellow A'), b.L('Kuning A menyala antara T1 selesai dan T2 selesai.', 'Yellow A is on between T1 done and T2 done.'));
      b.r([NO(on), NO(t2)], [OUT(ra)], b.L('Merah A', 'Red A'), b.L('Merah A menyala selama arah B mendapat giliran.', 'Red A is on while direction B has its turn.'));
      b.r([NO(t2), NC(t3)], [OUT(gb)], b.L('Hijau B', 'Green B'), b.L('Hijau B menyala setelah kuning A selesai.', 'Green B follows yellow A.'));
      b.r([NO(t3), NC(t4)], [OUT(yb)], b.L('Kuning B', 'Yellow B'), b.L('Kuning B menyala antara T3 dan T4.', 'Yellow B is on between T3 and T4.'));
      b.r([NO(on), NC(t2)], [OUT(rb)], b.L('Merah B', 'Red B'), b.L('Merah B menyala selama arah A mendapat giliran.', 'Red B is on while direction A has its turn.'));
      return b.project(b.L('Lampu lalu lintas', 'Traffic light'), '', 'traffic');
    },
  },
  {
    id: 'parking',
    category: 'general',
    title: { id: 'Penghitung parkir', en: 'Parking counter' },
    summary: { id: 'Hitung mobil masuk/keluar, lampu PENUH saat kapasitas tercapai.', en: 'Count cars in/out; FULL lamp when capacity is reached.' },
    params: [num('cap', 'Kapasitas', 'Capacity', 20, 1, 9999)],
    build: (p, lang) => {
      const b = new B(lang);
      const inS = b.input('SENS_IN', b.L('Sensor mobil masuk', 'Car-in sensor'), 'sensor');
      const outS = b.input('SENS_OUT', b.L('Sensor mobil keluar', 'Car-out sensor'), 'sensor');
      const rst = b.input('RESET', b.L('Reset hitungan', 'Reset count'));
      const cnt = b.word('COUNT', b.L('Jumlah mobil di dalam', 'Cars inside'));
      const gate = b.output('GATE_OPEN', b.L('Palang masuk boleh buka', 'Entry gate enabled'));
      const full = b.output('H_FULL', b.L('Lampu PENUH', 'FULL sign'));
      const cap = Number(p.cap);
      b.r([P(inS), CMP(tag(cnt), '<', k(cap))], [MATH('INC', cnt, tag(cnt))], b.L('Mobil masuk', 'Car in'),
        b.L('Setiap tepi naik sensor masuk menambah COUNT satu, selama belum penuh.', 'Each rising edge of the entry sensor adds one to COUNT while not full.'));
      b.r([P(outS), CMP(tag(cnt), '>', k(0))], [MATH('DEC', cnt, tag(cnt))], b.L('Mobil keluar', 'Car out'),
        b.L('Setiap tepi naik sensor keluar mengurangi COUNT satu, dan tidak pernah di bawah nol.', 'Each rising edge of the exit sensor subtracts one, never below zero.'));
      b.r([NO(rst)], [MATH('MOV', cnt, k(0))], b.L('Reset', 'Reset'), b.L('RESET mengisi COUNT dengan 0.', 'RESET loads 0 into COUNT.'));
      b.r([CMP(tag(cnt), '>=', k(cap))], [OUT(full)], b.L('Penuh', 'Full'), b.L(`Lampu PENUH menyala saat COUNT ≥ ${cap}.`, `FULL sign is on when COUNT ≥ ${cap}.`));
      b.r([NC(full)], [OUT(gate)], b.L('Palang', 'Gate'), b.L('Palang hanya boleh dibuka jika parkir belum penuh.', 'The gate may open only when the car park is not full.'));
      return b.project(b.L('Penghitung parkir', 'Parking counter'), '', 'parking');
    },
  },
  {
    id: 'stair-light',
    category: 'general',
    title: { id: 'Lampu tangga (toggle + auto off)', en: 'Stair light (toggle + auto off)' },
    summary: { id: 'Dua tombol di atas/bawah tangga, sekali tekan nyala, tekan lagi mati, mati sendiri setelah T.', en: 'Two buttons, press to toggle, turns itself off after T.' },
    params: [sec('auto', 'Mati otomatis setelah', 'Auto off after', 60, 1, 3600)],
    build: (p, lang) => {
      const b = new B(lang);
      const pb1 = b.input('PB_DOWN', b.L('Tombol bawah tangga', 'Downstairs button'));
      const pb2 = b.input('PB_UP', b.L('Tombol atas tangga', 'Upstairs button'));
      const pulse = b.mem('M_PULSE', b.L('Pulsa satu scan saat tombol ditekan', 'One-scan pulse on press'));
      const lamp = b.output('LAMP', b.L('Lampu tangga', 'Stair lamp'));
      const t = b.timer('T_OFF', b.L('Timer mati otomatis', 'Auto-off timer'));
      b.r([OR(P(pb1), P(pb2))], [OUT(pulse)], b.L('Pulsa tombol', 'Button pulse'),
        b.L('Kontak tepi naik membuat M_PULSE ON hanya satu scan per tekan, sehingga satu tekan sama dengan satu kali toggle.', 'Rising-edge contacts make M_PULSE on for one scan per press, so one press is one toggle.'));
      b.r([OR([NO(pulse), NC(lamp)], [NC(pulse), NO(lamp)]), NC(t)], [OUT(lamp)], b.L('Toggle lampu', 'Toggle lamp'),
        b.L('Rangkaian XOR: pulsa membalik status lampu. Saat T_OFF selesai, lampu dipaksa mati.', 'XOR circuit: the pulse flips the lamp. When T_OFF is done the lamp is forced off.'));
      b.r([NO(lamp)], [TON(t, ms(p.auto))], b.L('Auto off', 'Auto off'), b.L(`Selama lampu menyala, T_OFF menghitung ${p.auto} detik.`, `While the lamp is on T_OFF counts ${p.auto} s.`));
      return b.project(b.L('Lampu tangga', 'Stair light'), '', 'stair-light');
    },
  },
  {
    id: 'alarm',
    category: 'general',
    title: { id: 'Alarm dengan acknowledge', en: 'Alarm with acknowledge' },
    summary: { id: 'Lampu kedip + buzzer saat gangguan, ACK mematikan buzzer, RESET setelah normal.', en: 'Flashing lamp + buzzer on fault, ACK silences, RESET once cleared.' },
    params: [num('blink', 'Periode kedip', 'Blink period', 500, 100, 2000)],
    build: (p, lang) => {
      const b = new B(lang);
      const fault = b.input('FAULT', b.L('Sinyal gangguan', 'Fault signal'), 'switch');
      const ack = b.input('ACK', b.L('Tombol acknowledge', 'Acknowledge button'));
      const rst = b.input('RESET', b.L('Tombol reset', 'Reset button'));
      const al = b.mem('M_ALARM', b.L('Alarm aktif', 'Alarm active'));
      const acked = b.mem('M_ACKED', b.L('Sudah di-acknowledge', 'Acknowledged'));
      const ta = b.timer('T_ON', b.L('Kedip: fase nyala', 'Blink: on phase'));
      const tb = b.timer('T_OFF', b.L('Kedip: fase mati', 'Blink: off phase'));
      const lamp = b.output('H_ALARM', b.L('Lampu alarm', 'Alarm lamp'));
      const horn = b.output('BUZZER', b.L('Buzzer', 'Buzzer'));
      const bl = Number(p.blink);
      b.r([P(fault)], [SET(al)], b.L('Gangguan masuk', 'Fault in'), b.L('Tepi naik gangguan mengaktifkan alarm (tetap aktif walau gangguan hilang sesaat).', 'A fault rising edge latches the alarm (it stays even if the fault clears briefly).'));
      b.r([NO(al), NO(ack)], [SET(acked)], b.L('Acknowledge', 'Acknowledge'), b.L('ACK menandai alarm sudah diketahui operator.', 'ACK marks the alarm as seen by the operator.'));
      b.r([NO(rst), NC(fault)], [RST(al), RST(acked)], b.L('Reset', 'Reset'), b.L('RESET hanya berlaku jika gangguan sudah hilang.', 'RESET only works once the fault has cleared.'));
      b.r([NC(tb)], [TON(ta, bl)], b.L('Osilator 1', 'Oscillator 1'), b.L('Dua timer saling mereset untuk membuat kedipan.', 'Two timers reset each other to make the blink.'));
      b.r([NO(ta)], [TON(tb, bl)], b.L('Osilator 2', 'Oscillator 2'), b.L('T_OFF mulai setelah T_ON selesai, lalu me-reset T_ON.', 'T_OFF starts after T_ON, then resets T_ON.'));
      b.r([NO(al), OR([NC(acked), NO(ta)], NO(acked))], [OUT(lamp)], b.L('Lampu alarm', 'Alarm lamp'), b.L('Lampu berkedip sebelum ACK, dan menyala tetap setelah ACK.', 'Lamp flashes before ACK and is steady after ACK.'));
      b.r([NO(al), NC(acked)], [OUT(horn)], b.L('Buzzer', 'Buzzer'), b.L('Buzzer bunyi sampai ACK ditekan.', 'Buzzer sounds until ACK is pressed.'));
      return b.project(b.L('Alarm + acknowledge', 'Alarm + acknowledge'), '', 'alarm');
    },
  },
];

export function defaults(t: Template): Params {
  return Object.fromEntries(t.params.map((p) => [p.key, p.default]));
}

export const templateById = (id: string) => TEMPLATES.find((t) => t.id === id);
