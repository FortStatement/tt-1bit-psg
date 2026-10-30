`default_nettype none
`timescale 1ns / 1ps

module tb ();

  initial begin
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] ui_in;
  reg [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;
`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  wire voice0 = uo_out[0];
  wire audio = uo_out[7];

  reg [15:0] pcm_window = 16'd208;
  reg [15:0] pcm_phase = 16'd0;
  reg [15:0] pcm_count = 16'd0;
  reg [15:0] pcm = 16'd0;
  reg pcm_strobe = 1'b0;
  always @(posedge clk) begin
    if (!rst_n) begin
      pcm_count <= 16'd0;
      pcm_phase <= 16'd0;
    end else if (pcm_phase == pcm_window - 1) begin
      pcm <= pcm_count + audio;
      pcm_count <= 16'd0;
      pcm_phase <= 16'd0;
      pcm_strobe <= ~pcm_strobe;
    end else begin
      pcm_count <= pcm_count + audio;
      pcm_phase <= pcm_phase + 1;
    end
  end

  tt_um_fortstatement_onebit_psg user_project (
`ifdef GL_TEST
      .VPWR(VPWR),
      .VGND(VGND),
`endif
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

endmodule
