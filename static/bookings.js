$(function() {

  // test to ensure jQuery is working
  console.log("whee!")

  // disable refresh button
  // $("#refresh-btn").prop("disabled", true)
  


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
  });
})
