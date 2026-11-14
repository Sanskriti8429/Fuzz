# Fuzz

**Catch the spark before it becomes a fire.**

Fuzz is a low-cost, multi-sensor early-warning device for electrical faults in homes. It installs at the distribution board and watches a branch circuit through independent sensors. It flags a developing fault early, cuts the supply if it escalates, and uses machine learning to estimate which appliance is likely at risk and roughly how far along the wiring the problem is.

> **Project type:** simulation-based capstone. The schematic is complete in KiCad. Circuit values are being confirmed by SPICE simulation, and the machine-learning models are trained on public datasets passed through simulated front-end and cable models. No hardware has been built or measured. See [Limitations](#limitations).

---

## Why this project

Most electrical fires start small: a loose terminal that arcs, insulation that slowly leaks, a joint that heats up. Standard MCBs and RCDs look at one signal and act only once the fault is already serious. Fuzz targets the gap between "normal" and "tripped", and tells the homeowner what is causing the threat.

## What it senses

Four warning channels and one supply-monitoring channel feed a single ESP32:

- **RF arc:** radio noise from sparking at loose joints. Loop antenna, LC tank, envelope detector.
- **Leakage current:** insulation breakdown. Current transformer (ZMCT103C), amplifier, rectifier.
- **di/dt:** very fast current rise, the signature of a short circuit. Coil, integrator, comparator.
- **Temperature:** hot, loose connections. NTC thermistor divider.
- **Mains voltage (supply monitoring):** over- and under-voltage and frequency. ZMPT101B voltage sensing module.

## Detection logic

Two tiers, evaluated on the ESP32:

- **WARNING (predictive):** two or more channels trend upward together over a rolling window. The user is notified and nothing is cut.
- **TRIP (protective):** a hard limit is crossed, or the di/dt comparator fires. The relay module opens the supply immediately, without depending on Wi-Fi or the server.

Thresholds are derived in the calculations report in `docs/`.

## Machine learning

The AI is what turns "something is wrong" into "something is wrong, probably here". Planned outputs:

- **Fault state:** normal, warning or trip.
- **Appliances at risk:** several appliances can run on one branch, so this is a multi-label problem.
- **Probable distance:** estimated distance in metres from the board along the wiring, reported with a confidence range (for example "about 10 m, likely 8 to 12 m").

How the training data will be built (planned, not yet implemented):

1. Real appliance and arc current signatures come from public datasets (see [Datasets](#datasets)).
2. Multi-appliance cases are made by adding single-appliance currents together (Kirchhoff's current law), as in the NILM literature.
3. Those signals are passed through a simulated model of Fuzz's own sensing circuits and a cable model of 1 to 20 m. This produces the features Fuzz's ESP32 would actually see, together with distance labels.
4. Models are trained on those features and tested across datasets.

The Ferracuti windows contain the absolute value of the current, not a signed waveform, so how they pass through the sensing-circuit model is still to be decided.

Models to compare:

- **Tree-based baselines:** Random Forest and XGBoost.
- **Deep models:** a 1D CNN, a ROCKET-type model, and a CNN-Transformer.
- **Multi-task model:** one shared model that outputs fault state, appliances and distance, compared against separate single-task models.

Also planned: a channel ablation (retrain with each sensor removed to show what each one contributes), SHAP explanations for each alert, and alert thresholds that treat false alarms as more costly than missed warnings.

The four-channel fusion itself is rule-based, because no public dataset contains all the sensor signals together.

## System architecture

*To be added.*

## Operator dashboard and client app

Planned, built in plain HTML and JavaScript:

- **Operator dashboard:** live status of every unit, the sensor readings over time, model outputs with confidence, alert history and settings.
- **Client mobile view:** a simple risk indicator, a plain-language message such as "arc activity, likely microwave, about 10 m away (8 to 12 m)", notifications and advice.

Until hardware exists, a simulator script plays the ESP32's role and sends scenarios (normal use, an arc at a given distance, rising leakage, overheating) to the backend.

## Repository structure

```
hardware/
  kicad/          Full-system schematic (KiCad), exported PDF, BOM
  simulation/     SPICE simulations of the analog stages
firmware/         ESP32 fusion and trip logic
ml/
  data/           Datasets (downloaded locally, not committed)
  *.py            Exploration, data generation, training, evaluation
backend/          Inference server (planned)
dashboard/        Operator dashboard and client view (planned)
demo/             Demo video scripts
docs/             Calculations report, schematic PDF
requirements.txt  Python packages
```

## Status

- [x] Sensing strategy and system design
- [x] Full-system schematic in KiCad (ERC run, 0 violations, with some checks ignored)
- [x] Exported schematic PDF and BOM
- [x] Analog stages simulated in SPICE and component values confirmed
- [ ] Cable and arc-source model for the distance data
- [x] Arc datasets (Ferracuti, Lorraine) downloaded and explored
- [ ] Appliance datasets (PLAID, COOLL) downloaded and explored
- [x] Arc classifier baseline with same-dataset and cross-dataset evaluation
- [ ] Training-data generation pipeline
- [ ] Models trained, compared and evaluated across datasets
- [ ] ESP32 fusion logic
- [ ] Backend, ESP32 simulator, operator dashboard and client view
- [ ] Calculations report
- [ ] Demo video

## Datasets

Datasets are not stored in this repo. They are downloaded locally into `ml/data/`. Ferracuti and Lorraine are CC BY 4.0, so credit the authors. Licences for PLAID, COOLL and the TI set are still to be confirmed.

- **Arc faults (main):** Ferracuti et al., 2025. Series arc current signatures from 13 load types, 230 V / 50 Hz, IEC 62606. Windows of absolute current, 5 to 50 ms at 10 to 100 kHz, with 2, 5 or 14 class labels. [doi.org/10.5281/zenodo.15279701](https://doi.org/10.5281/zenodo.15279701)
- **Arc faults (cross-dataset test):** Series AC arc fault data from a 230 V / 50 Hz domestic network, University of Lorraine and Huaqiao University. Line current and arc voltage at 1 MS/s for 13 appliance and arc-type recordings. Arc labels come from the arc voltage. [zenodo.org/record/3997337](https://zenodo.org/record/3997337)
- **Appliance identification (main):** PLAID, appliance voltage and current at 30 kHz, including aggregated recordings. Scientific Data, 2020, doi 10.1038/s41597-020-0389-7.
- **Appliance identification (validation):** COOLL, 42 appliances sampled at 100 kHz. arXiv 1611.05803.
- **Optional:** Texas Instruments `ac_arc_fault_log300`, for testing false alarms from masking loads such as dimmers and drills.

No public dataset contains distance, so distance labels come from the simulated cable model.

## Results

- **Arc classifier, same-dataset (Ferracuti, 20 ms windows at 10 kHz, XGBoost):** 98.4% accuracy, 99.4% of arc windows detected, 2.1% false alarms.
- **Arc classifier, cross-dataset (trained on Ferracuti, tested on Lorraine, 457 arc and 1104 normal windows):** 68.9% of arc windows detected with 4.4% false alarms when downsampling with an anti-alias filter, or 78.8% detected with 9.4% false alarms with plain subsampling. Carbonized-path arcs on resistive and drill loads are detected at about 98%. Vacuum cleaner and open-contact arcs are much weaker, and the vacuum cleaner causes most false alarms.
- **Appliance identification, single appliance (PLAID, 11 types, split by house):** 76.6% exact accuracy and 94.1% accuracy at family level (heating, motor-driven, electronics, microwave). Heater is often mistaken for hairdryer, and fan for air conditioner, because their current shapes are similar. A random split gives 98 to 99%, which is inflated because recordings from the same house land on both sides.
- **Appliance identification, several at once (PLAID aggregated, split in blocks of records):** macro F1 0.85 over 13 types. With one appliance running the exact set is right in 98% of windows, with two running 53% (84% of the true appliances are in the top two guesses), and with three running 15% (76% in the top three).
- **Appliance identification, cross-dataset:** trained only on synthetic mixtures of single-appliance recordings from 2013 to 2014 houses and tested on real 2017 lab mixtures, macro F1 is about 0.40. Lamp, laptop and fridge transfer (F1 0.87, 0.81, 0.62), but air conditioner and fan do not (F1 0.00).

Windows are labelled as arc when the arc-voltage RMS exceeds 5 V and the appliance is conducting (current RMS above 0.3 A). The 457 arc windows include 47 low-voltage Res7.9A windows (arc voltage up to 5.9 V RMS) whose labels are doubtful and none of which were detected.

## Limitations

- **Simulation only.** Nothing has been built or measured. Circuit values are confirmed by simulation, not on hardware.
- **Distance is simulated.** Distance labels come from a cable model, so accuracy is only as good as that model. Real wiring has junctions, branches and other loads. Distance is reported as a probable range, and field validation is future work.
- **Appliance guesses are probabilities.** With several appliances running, one can mask another. Results are reported with confidence and a confusion matrix.
- **Dataset domain gap.** Public datasets were recorded at the appliance, not through a long cable, and with different equipment from Fuzz's sensors.
- **Rule-based fusion.** Fusion thresholds come from calculation and simulation, not from field data.
- **Single-channel current classifiers did not transfer well across datasets.** This motivates, but does not yet prove, the multi-sensor approach.
- **Not a certified device.** This is an educational prototype and must not be used as a safety product.
- **Simulation assumptions.** The antenna source impedance, the di/dt coil inductance and the NTC beta (3950) are assumed, not measured. The RF channel has no high-pass, so mains pickup is amplified. The leakage rectifier does not hold a DC level, so the firmware samples the waveform instead. The di/dt trip has only about four times margin over normal load, so dimmers and motor starts may need extra handling.
- **Appliance identity is device-specific.** Models recognise appliance families well but do not reliably recognise unseen individual devices. A deployed unit would need to learn each household's appliances. PLAID is also recorded on 120 V, 60 Hz mains, not 230 V, 50 Hz.

## Simulation results

The four analog stages were simulated in LTspice (netlists in `hardware/simulation/`). The simulations changed two component values: U1 is now a roughly 10 MHz rail-to-rail op-amp (TLV9062) instead of a TS912, and R9 is 100k instead of 1M.

- **RF arc channel:** the LC tank resonates at about 970 kHz. Gain at resonance depends on the antenna's source impedance (about +36 dB at 10 ohms, about +23 dB at 50 ohms, untuned at 200 ohms). With a 10 ohm source the detector responds to signals of about 1 to 2 mV and saturates above about 15 mV.
- **Leakage channel:** with R9 at 100k the amplifier has a gain of about 101 and tolerates a few millivolts of offset. A 30 mA leakage gives a swing of about 70 to 80 mV.
- **di/dt channel:** with an assumed 1 microhenry coil, the comparator trips at about 16.5 kA/s and ignores normal 50 Hz load current. The ESP32 must catch the pulse with a falling-edge interrupt.
- **Temperature channel:** the divider output is 0.76 V at 0 C, 1.65 V at 25 C, 2.64 V at 60 C and 3.08 V at 100 C.

## Getting started

```
python -m venv .venv
.venv\Scripts\Activate.ps1   # or: source .venv/bin/activate
pip install -r requirements.txt
```