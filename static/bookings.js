var addrLookup = {
  "SCDF HQ":"91 Ubi Ave 4 S(408827)",
  "CDA":"101 Jalan Bahar S(649734)",
  "HTA":"501 Old Choa Chu Kang Rd S(698928)"}
function getAddress(k){
  return addrLookup[k];
}


//$("#location_select").change(function() {
$( document ).on("change", "#location_select", function() {

  // grab value
  var location_id = $("#location_select").val();
  	var dataString = $("#htmbForm").serialize();

  // send value via POST to URL /<department_id>
  var get_request = $.ajax({
    type: 'GET',
  		data: dataString,
    url: '/slotsfor/' + location_id + '/'
  });

  // handle response
  get_request.done(function(data){

    // data
    console.log(data)

      // add values to list 
      var option_list = [["", "Choose Date & Time"]].concat(data);
      $("#slot_select").empty();
        for (var i = 0; i < option_list.length; i++) {
          $("#slot_select").append(
            $("<option></option>").attr("value", option_list[i][0]).text(option_list[i][1]));
        }
      // show model list
      $("#slot_select").show();
    });
    //show address
    $('.addressText').text(getAddress(location_id));
  });
