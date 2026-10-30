`default_nettype none

module tt_um_fortstatement_onebit_psg (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  reg [1:0] wr_sync;
  always @(posedge clk) begin
    if (!rst_n) wr_sync <= 2'b00;
    else        wr_sync <= {wr_sync[0], uio_in[4]};
  end
  wire we = wr_sync[1];

  wire [1:0] sel = uio_in[3:2];
  wire [1:0] reg_addr = uio_in[1:0];
  wire [7:0] data = ui_in;

  reg [7:0] freq_lo;
  always @(posedge clk) begin
    if (!rst_n)                   freq_lo <= 8'd0;
    else if (we && reg_addr == 0) freq_lo <= data;
  end

  reg [1:0] slot;
  reg [6:0] rot;
  always @(posedge clk) begin
    if (!rst_n) begin
      slot <= 2'd0;
      rot  <= 7'd0;
    end else if (slot == 2'd2) begin
      slot <= 2'd0;
      rot  <= rot + 7'd1;
    end else begin
      slot <= slot + 2'd1;
    end
  end

  wire [7:0] tick;
  assign tick[7] = 1'b1;
  genvar i;
  generate
    for (i = 6; i >= 0; i = i - 1) begin : g_tick
      assign tick[i] = tick[i+1] & ~rot[6-i];
    end
  endgenerate

  reg [16:0] lfsr;
  always @(posedge clk) begin
    if (!rst_n) lfsr <= 17'd1;
    else        lfsr <= {lfsr[15:0], lfsr[16] ^ lfsr[13]};
  end

  localparam [46:0] VOICE_RESET = 47'd2 << 28;

  reg  [46:0] ring [0:2];
  wire [46:0] head_next;
  wire [2:0]  head_oct;
  wire [7:0]  head_level;
  wire        head_pulse;
  wire        hit = we && sel == slot;

  voice v (
      .state  (ring[0]),
      .tick   (tick[head_oct]),
      .noise  (lfsr[3:0]),
      .we_freq(hit && reg_addr == 1),
      .freq_d ({data[3:0], freq_lo}),
      .oct_d  (data[6:4]),
      .we_ctrl(hit && reg_addr == 2),
      .ctrl_d (data),
      .we_sync(hit && reg_addr == 3),
      .next   (head_next),
      .oct    (head_oct),
      .level  (head_level),
      .pulse  (head_pulse)
  );

  reg [2:0] pulse;
  always @(posedge clk) begin
    if (!rst_n) begin
      ring[0] <= VOICE_RESET;
      ring[1] <= VOICE_RESET;
      ring[2] <= VOICE_RESET;
      pulse   <= 3'd0;
    end else begin
      ring[0] <= ring[1];
      ring[1] <= ring[2];
      ring[2] <= head_next;
      pulse[slot] <= head_pulse;
    end
  end

  reg [7:0] sd_acc;
  reg       audio;
  always @(posedge clk) begin
    if (!rst_n) begin
      sd_acc <= 8'd0;
      audio  <= 1'b0;
    end else begin
      {audio, sd_acc} <= {1'b0, sd_acc} + {1'b0, head_level};
    end
  end

  assign uo_out  = {audio, audio, 1'b0, lfsr[0], ^pulse, pulse};
  assign uio_out = {audio, 7'd0};
  assign uio_oe  = 8'b1000_0000;

  wire _unused = &{ena, uio_in[7:5], data[7], 1'b0};

endmodule
