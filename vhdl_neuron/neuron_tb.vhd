-- =============================================================================
-- neuron_tb.vhd  -  Testbench for neuron.vhd
--
-- Drives four test vectors and checks the output after the 2-cycle pipeline.
--
-- Test cases
--   1. Normal positive result  : 2*3 + 1*4 + (-1)*0 + 0*0 + 1  =  11  -> 11
--   2. ReLU clips negative sum : (-5)*10 + 0 + 0 + 0 + 0       = -50  ->  0
--   3. Saturation high         : 100*2 + 100*2 + 0 + 0 + 27     = 427  -> 127
--   4. All-zero inputs         : 0 * ...  + 0                   =   0  ->   0
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity neuron_tb is
end entity neuron_tb;

architecture sim of neuron_tb is

  -- Helper: integer -> 8-bit signed SLV
  function to_slv8(val : integer) return std_logic_vector is
  begin
    return std_logic_vector(to_signed(val, 8));
  end function;

  -- DUT signals
  signal clk  : std_logic := '0';
  signal rst  : std_logic := '1';
  signal x0, x1, x2, x3 : std_logic_vector(7 downto 0) := (others => '0');
  signal w0, w1, w2, w3 : std_logic_vector(7 downto 0) := (others => '0');
  signal bias            : std_logic_vector(7 downto 0) := (others => '0');
  signal y               : std_logic_vector(7 downto 0);
  signal valid           : std_logic;

  constant T_CLK : time := 10 ns;

begin

  -- DUT
  uut : entity work.neuron
    port map (
      clk  => clk,
      rst  => rst,
      x0   => x0,  x1 => x1,  x2 => x2,  x3 => x3,
      w0   => w0,  w1 => w1,  w2 => w2,  w3 => w3,
      bias => bias,
      y    => y,
      valid=> valid
    );

  -- Clock
  clk <= not clk after T_CLK / 2;

  -- Stimulus
  stimulus : process
    -- Apply inputs, wait 2 cycles for the pipeline, then check y.
    -- 'tc_name' replaces the reserved keyword 'label'.
    procedure apply_and_check(
      i_x0, i_x1, i_x2, i_x3 : integer;
      i_w0, i_w1, i_w2, i_w3 : integer;
      i_bias                  : integer;
      expected                : integer;
      tc_name                 : string
    ) is
      variable got : integer;
    begin
      wait until rising_edge(clk);
      x0   <= to_slv8(i_x0);  x1 <= to_slv8(i_x1);
      x2   <= to_slv8(i_x2);  x3 <= to_slv8(i_x3);
      w0   <= to_slv8(i_w0);  w1 <= to_slv8(i_w1);
      w2   <= to_slv8(i_w2);  w3 <= to_slv8(i_w3);
      bias <= to_slv8(i_bias);

      -- 2-cycle pipeline: wait for stage-1 then stage-2 to complete.
      -- The extra 'wait for 1 ns' skips past the delta cycles at the
      -- second rising edge so we read y AFTER stage-2 has updated it.
      wait until rising_edge(clk);   -- stage-1 captures inputs
      wait until rising_edge(clk);   -- stage-2 fires; y_r updated in delta
      wait for 1 ns;                 -- let delta cycles propagate

      got := to_integer(signed(y));

      assert got = expected
        report "[FAIL] " & tc_name &
               "  got=" & integer'image(got) &
               "  expected=" & integer'image(expected)
        severity error;

      if got = expected then
        report "[PASS] " & tc_name & "  y=" & integer'image(got);
      end if;
    end procedure;

  begin
    -- Release reset
    wait until rising_edge(clk);
    wait until rising_edge(clk);
    rst <= '0';

    -- TC1: 2*3 + 1*4 + (-1)*0 + 0*0 + bias 1 = 6+4+0+0+1 = 11
    apply_and_check(
      i_x0 => 2,  i_x1 => 1,  i_x2 => 0,  i_x3 => 0,
      i_w0 => 3,  i_w1 => 4,  i_w2 => -1, i_w3 => 0,
      i_bias   => 1,
      expected => 11,
      tc_name  => "TC1 - normal positive result"
    );

    -- TC2: (-5)*10 = -50, ReLU -> 0
    apply_and_check(
      i_x0 => -5, i_x1 => 0,  i_x2 => 0,  i_x3 => 0,
      i_w0 => 10, i_w1 => 0,  i_w2 => 0,  i_w3 => 0,
      i_bias   => 0,
      expected => 0,
      tc_name  => "TC2 - ReLU clamps negative to 0"
    );

    -- TC3: 100*2 + 100*2 + 0 + 0 + 27 = 427 -> saturate to 127
    apply_and_check(
      i_x0 => 100, i_x1 => 100, i_x2 => 0, i_x3 => 0,
      i_w0 => 2,   i_w1 => 2,   i_w2 => 0, i_w3 => 0,
      i_bias   => 27,
      expected => 127,
      tc_name  => "TC3 - positive saturation to 127"
    );

    -- TC4: all zeros -> 0
    apply_and_check(
      i_x0 => 0, i_x1 => 0, i_x2 => 0, i_x3 => 0,
      i_w0 => 0, i_w1 => 0, i_w2 => 0, i_w3 => 0,
      i_bias   => 0,
      expected => 0,
      tc_name  => "TC4 - all zeros"
    );

    report "=== Testbench complete ===" severity note;
    wait;
  end process stimulus;

end architecture sim;
