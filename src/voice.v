`default_nettype none

module voice (
    input  wire [46:0] state,
    input  wire        tick,
    input  wire [3:0]  noise,
    input  wire        we_freq,
    input  wire [11:0] freq_d,
    input  wire [2:0]  oct_d,
    input  wire        we_ctrl,
    input  wire [7:0]  ctrl_d,
    input  wire        we_sync,
    output wire [46:0] next,
    output wire [2:0]  oct,
    output wire [7:0]  level,
    output wire        pulse
);

  localparam WAVE_PULSE = 2'd0;
  localparam WAVE_SAW   = 2'd1;
  localparam WAVE_TRI   = 2'd2;
  localparam WAVE_NOISE = 2'd3;

  wire [11:0] freq = state[46:35];
  assign      oct  = state[34:32];
  wire [1:0]  wave = state[31:30];
  wire [1:0]  duty = state[29:28];
  wire [3:0]  vol  = state[27:24];
  wire [19:0] acc  = state[23:4];
  wire [3:0]  nz   = state[3:0];

  wire [16:0] acc_lo = {1'b0, acc[15:0]} + {5'b0, freq};
  wire        noise_clk = acc_lo[16];
  wire [3:0]  acc_hi = acc[19:16] + {3'b0, noise_clk};

  wire [19:0] acc_next = we_sync ? 20'd0 : tick ? {acc_hi, acc_lo[15:0]} : acc;
  wire [3:0]  nz_next  = (!we_sync && tick && noise_clk) ? noise : nz;

  assign next = {
    we_freq ? {freq_d, oct_d} : {freq, oct},
    we_ctrl ? ctrl_d : {wave, duty, vol},
    acc_next,
    nz_next
  };

  wire [3:0] phase = acc[19:16];

  reg [3:0] thr;
  always @(*) begin
    case (duty)
      2'd0:    thr = 4'd2;
      2'd1:    thr = 4'd4;
      2'd2:    thr = 4'd8;
      default: thr = 4'd12;
    endcase
  end
  wire pulse_hi = phase < thr;

  reg [3:0] shape;
  always @(*) begin
    case (wave)
      WAVE_PULSE: shape = {4{pulse_hi}};
      WAVE_SAW:   shape = phase;
      WAVE_TRI:   shape = acc[19] ? ~acc[18:15] : acc[18:15];
      WAVE_NOISE: shape = nz;
      default:    shape = 4'd0;
    endcase
  end

  assign level = shape * vol;
  assign pulse = pulse_hi & (vol != 4'd0);

endmodule
