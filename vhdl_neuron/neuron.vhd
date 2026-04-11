-- =============================================================================
-- neuron.vhd
--
-- Single artificial neuron with ReLU activation.
--
--   y = ReLU( w0·x0 + w1·x1 + w2·x2 + w3·x3 + bias )
--
-- Data representation
--   All inputs, weights and bias are Q1.7  (8-bit signed, range –128 … 127).
--   The output y is the same format: 8-bit signed, but clamped to [0, 127]
--   because ReLU zeros the negative half.
--
-- Pipeline (2 clock cycles latency)
--   Cycle 1 – Multiply  : compute four 16-bit products simultaneously
--   Cycle 2 – Accumulate: sum products + bias → 20-bit; saturate; ReLU
--
-- Port list
--   clk   – rising-edge clock
--   rst   – synchronous active-high reset
--   x0..3 – four 8-bit signed inputs   (std_logic_vector)
--   w0..3 – four 8-bit signed weights  (std_logic_vector)
--   bias  – 8-bit signed bias          (std_logic_vector)
--   y     – 8-bit signed output        (std_logic_vector)
--   valid – pulses high the cycle the first valid y appears, stays high
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity neuron is
  port (
    clk  : in  std_logic;
    rst  : in  std_logic;
    -- Inputs (8-bit signed, represented as std_logic_vector)
    x0   : in  std_logic_vector(7 downto 0);
    x1   : in  std_logic_vector(7 downto 0);
    x2   : in  std_logic_vector(7 downto 0);
    x3   : in  std_logic_vector(7 downto 0);
    -- Weights (8-bit signed)
    w0   : in  std_logic_vector(7 downto 0);
    w1   : in  std_logic_vector(7 downto 0);
    w2   : in  std_logic_vector(7 downto 0);
    w3   : in  std_logic_vector(7 downto 0);
    -- Bias (8-bit signed)
    bias : in  std_logic_vector(7 downto 0);
    -- Output
    y    : out std_logic_vector(7 downto 0);
    valid: out std_logic
  );
end entity neuron;

architecture rtl of neuron is

  -- ── Internal bit-widths ──────────────────────────────────────────────────
  -- Product:  8 × 8 = 16 bits
  -- Sum:      4 × 16-bit products → needs 18 bits; add 8-bit bias → 19 bits.
  --           We use 20 bits for a generous margin.
  constant PROD_W : positive := 16;
  constant SUM_W  : positive := 20;

  -- ── Stage-1 registers (multiply) ────────────────────────────────────────
  signal p0_r, p1_r, p2_r, p3_r : signed(PROD_W-1 downto 0);
  signal bias_r                  : signed(7 downto 0);
  signal s1_valid                : std_logic;

  -- ── Stage-2 registers (accumulate + activate) ───────────────────────────
  signal acc   : signed(SUM_W-1 downto 0);
  signal y_r   : signed(7 downto 0);
  signal s2_valid : std_logic;

begin

  -- ==========================================================================
  -- Stage 1 – Multiply inputs by weights
  -- ==========================================================================
  stage1 : process(clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        p0_r    <= (others => '0');
        p1_r    <= (others => '0');
        p2_r    <= (others => '0');
        p3_r    <= (others => '0');
        bias_r  <= (others => '0');
        s1_valid <= '0';
      else
        p0_r    <= signed(x0) * signed(w0);
        p1_r    <= signed(x1) * signed(w1);
        p2_r    <= signed(x2) * signed(w2);
        p3_r    <= signed(x3) * signed(w3);
        bias_r  <= signed(bias);
        s1_valid <= '1';
      end if;
    end if;
  end process stage1;

  -- ==========================================================================
  -- Stage 2 – Accumulate, saturate, ReLU
  -- ==========================================================================
  stage2 : process(clk)
    variable sum_v : signed(SUM_W-1 downto 0);
    variable sat_v : signed(7 downto 0);
  begin
    if rising_edge(clk) then
      if rst = '1' then
        y_r      <= (others => '0');
        s2_valid <= '0';
      else
        -- ── Accumulate ──────────────────────────────────────────────────
        -- Sign-extend each 16-bit product and the 8-bit bias to SUM_W bits.
        sum_v := resize(p0_r, SUM_W)
               + resize(p1_r, SUM_W)
               + resize(p2_r, SUM_W)
               + resize(p3_r, SUM_W)
               + resize(bias_r, SUM_W);

        -- ── Saturate to 8-bit signed (–128 … 127) ───────────────────────
        if sum_v > to_signed(127, SUM_W) then
          sat_v := to_signed(127, 8);
        elsif sum_v < to_signed(-128, SUM_W) then
          sat_v := to_signed(-128, 8);
        else
          sat_v := resize(sum_v, 8);
        end if;

        -- ── ReLU : max(0, sat_v) ─────────────────────────────────────────
        if sat_v < 0 then
          y_r <= (others => '0');   -- clamp negative values to 0
        else
          y_r <= sat_v;
        end if;

        s2_valid <= s1_valid;
      end if;
    end if;
  end process stage2;

  -- ── Output assignments ───────────────────────────────────────────────────
  y     <= std_logic_vector(y_r);
  valid <= s2_valid;

end architecture rtl;
